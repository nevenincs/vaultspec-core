"""The stateless discover/invoke gateway over the long-tail verb surface.

The hot-path tools are precisely schematized first-class tools. The remaining
long-tail verbs are reachable only through this two-tool gateway, so their
schemas never occupy standing context: ``discover`` searches the generated verb
catalog and returns ranked verb paths with their full parameter schemas on
demand, and ``invoke`` executes one cataloged verb by path against the installed
``vaultspec-core`` binary.

``invoke`` is a subprocess boundary, not an in-process dispatch: the long-tail
verbs are Typer-coupled (they render envelopes, print, and raise ``typer.Exit``)
so subprocessing the binary as a validated argv list is the only disposition
that covers them without unbounded plumbing, and it inherits the binary's
behavior verbatim. The security contract is strict: the verb path is validated
against the parsed catalog and the static denylist *before any process spawns*,
the command is always an argv list (never a shell string, never ``shell=True``),
``--target`` is injected from the server's resolved root, and ``--json`` is
appended only where the catalog says the verb supports it. Caller argument
values enter the command solely as discrete, validated argv items, so no
argument text can inject a shell command.

Argv hygiene alone is not the whole contract, because a few declared flags name
a command for the CLI to *execute* rather than data for it to process. For
those, discrete-argv-item handling is beside the point: the value is a command
either way. Two further measures cover them. The flags in
:data:`~vaultspec_core.mcp_server.catalog.BLOCKED_FLAGS` are refused whichever
verb declares them and are withheld from the schemas ``discover`` returns; and
every spawned child is marked through
:data:`~vaultspec_core.config.VAULTSPEC_MCP_GATEWAY_INVOCATION`, so the CLI itself knows
it has no terminal and declines to open an editor no matter which source the
editor command came from.

The child runs through anyio rather than a blocking :func:`subprocess.run`, so
the handler stays interruptible while the verb works and a cancelled or
timed-out call reaps the child instead of leaking it; :func:`_run_verb` holds
that contract.

Both handlers keep the copied-context isolation wrapper, and both declare
structured output through typed Pydantic return models.
"""

from __future__ import annotations

import functools
import json
import logging
import subprocess
import sys
from typing import TYPE_CHECKING, Any, cast

import anyio
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from ...config import VAULTSPEC_MCP_GATEWAY_INVOCATION, child_environment
from ...core.types import get_context as _get_ctx
from ..catalog import (
    BLOCKED_FLAGS,
    RESERVED_FLAGS,
    CatalogEntry,
    CatalogParseError,
    CommandCatalog,
    build_catalog,
)
from ..envelope import LeanResult, compact_result
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from pathlib import Path

    from anyio.abc import ByteReceiveStream, Process
    from mcp.server.mcpserver import MCPServer

logger = logging.getLogger(__name__)

__all__ = ["register_gateway_tools"]

#: Default wall-clock budget for a single ``invoke`` subprocess. The long tail
#: is low-frequency by definition, so a generous ceiling covers Python startup
#: plus the verb's own work without letting a wedged verb hang the handler.
_DEFAULT_TIMEOUT = 60.0

#: How long a child gets to exit after ``terminate()`` before it is killed.
_KILL_GRACE = 2.0


# ---------------------------------------------------------------------------
# discover output models
# ---------------------------------------------------------------------------


class FlagSchema(LeanResult):
    """One declared option of a discovered verb.

    Attributes:
        name: The canonical long-form flag, e.g. ``--feature``.
        takes_value: Whether the option consumes a following value.
        help: The option's help text.
    """

    name: str
    takes_value: bool
    help: str = ""


class ArgumentSchema(LeanResult):
    """One declared positional argument of a discovered verb.

    Attributes:
        name: The argument's declared name/metavar, for agent readability;
            positional order, not name, is what ``invoke`` renders.
        required: Whether the verb declares the argument as required.
        variadic: Whether the argument consumes the rest of the operands.
    """

    name: str
    required: bool
    variadic: bool = False


class VerbSchema(LeanResult):
    """A ranked verb returned by ``discover`` with its full parameter schema.

    Attributes:
        verb: The space-joined verb path, addressable by ``invoke``.
        description: The verb's curated help text from the CLI reference.
        score: The ranking score against the query (higher is closer).
        supports_json: Whether ``invoke`` will request and parse JSON output.
        flags: The verb's declared options.
        arguments: The verb's ordered positional operands, so a caller knows
            what to pass in ``invoke``'s ``positionals`` list and in what order.
    """

    verb: str
    description: str
    score: float
    supports_json: bool
    flags: list[FlagSchema] = Field(default_factory=list)
    arguments: list[ArgumentSchema] = Field(default_factory=list)


class DiscoverResult(LeanResult):
    """The whole-call result of a ``discover`` invocation.

    Attributes:
        query: The search string as submitted, echoed for traceability.
        count: The number of ranked verbs returned.
        verbs: The ranked verbs with their parameter schemas, best match first.
    """

    query: str
    count: int
    verbs: list[VerbSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# invoke output models
# ---------------------------------------------------------------------------


class InvokeError(LeanResult):
    """The structured failure payload of a verb that ran but did not succeed.

    Attributes:
        kind: The failure class - ``nonzero_exit``, ``json_parse``, or
            ``timeout``.
        exit_code: The subprocess exit code (``-1`` when the verb timed out
            before exiting).
        stderr: The captured standard error, folded in verbatim.
        message: A human-readable summary of the failure.
    """

    kind: str
    exit_code: int
    stderr: str = ""
    message: str


class InvokeResult(LeanResult):
    """The whole-call result of an ``invoke`` invocation.

    A verb that runs and exits non-zero is a *successful* ``invoke`` reporting
    ``ok == False`` with an :class:`InvokeError`; only an unknown or denied
    verb path, or an invalid argument, raises a protocol error before spawn.

    Attributes:
        verb: The verb path that was executed.
        ok: Whether the verb exited zero.
        exit_code: The subprocess exit code.
        format: ``"json"`` when the output was parsed as JSON, else ``"text"``.
        data: The parsed JSON payload when ``format == "json"`` and ``ok``.
        stdout: The raw captured stdout when the output was returned as text.
        error: The structured failure payload when ``ok`` is ``False``.
        command: The executed argv without the interpreter prefix, for
            transparency (e.g. ``["vaultspec-core", "vault", "list", ...]``).
    """

    verb: str
    ok: bool
    exit_code: int
    format: str
    data: Any | None = None
    stdout: str | None = None
    error: InvokeError | None = None
    command: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# catalog access
# ---------------------------------------------------------------------------


@functools.cache
def _load_catalog(reference_path: Path) -> CommandCatalog:
    """Build and memoize the catalog for a given reference path.

    The reference content is stable for a running server, so the parse plus
    Typer introspection runs once per resolved path and is reused across
    every gateway call.

    Args:
        reference_path: The resolved path to the CLI reference.

    Returns:
        The cached :class:`CommandCatalog`.
    """
    return build_catalog(reference_path)


def _reference_path() -> Path:
    """Resolve the CLI reference path from the active workspace context.

    The reference lives under the resolved ``.vaultspec`` directory, which is
    the parent of the templates directory the context exposes; nothing is
    hardcoded to an absolute location.

    Returns:
        The path to ``.vaultspec/reference/cli.md`` under the server root.
    """
    return _get_ctx().templates_dir.parent / "reference" / "cli.md"


def _active_catalog() -> CommandCatalog:
    """Load the catalog for the active workspace, refusing a broken install.

    A reference without the generated marker block leaves no verb addressable,
    so every ``discover`` and ``invoke`` call fails identically until the
    installation is repaired. That is a deterministic, remediable condition
    rather than a crash, and the SDK discards the text of anything that is not
    a ``ToolError`` - so the parse failure is translated here, at the tool
    boundary, and the caller learns to stop retrying and repair instead.

    The translation is deliberately narrow: only
    :class:`~vaultspec_core.mcp_server.catalog.CatalogParseError` is caught, so
    an unexpected ``ValueError`` from the Typer introspection inside
    :func:`build_catalog` stays a crash and keeps its message suppressed.

    Returns:
        The cached :class:`CommandCatalog` for the resolved reference path.

    Raises:
        ToolError: When the shipped CLI reference carries no command-inventory
            marker block.
    """
    try:
        return _load_catalog(_reference_path())
    except CatalogParseError as exc:
        msg = (
            f"{exc}. No verb is addressable until the installation is "
            f"repaired: reinstall vaultspec-core, or regenerate the reference "
            f"with 'vaultspec-core spec reference generate'."
        )
        raise ToolError(msg) from exc


# ---------------------------------------------------------------------------
# argv construction
# ---------------------------------------------------------------------------


def _build_argv(
    entry: CatalogEntry,
    supports_json: bool,
    arguments: dict[str, Any],
    positionals: list[str],
    root_dir: Path,
) -> list[str]:
    """Build the interpreter-prefixed argv list for a validated verb call.

    The interpreter and module entry mirror how the server itself runs
    (``sys.executable -m vaultspec_core``), so the gateway invokes the same
    command surface whether installed as a console script or run from this
    development environment. ``--target`` is injected at the global position;
    the caller's ordered positionals are placed immediately after the verb
    path (their canonical operand slots, ahead of any options so a value-flag
    never swallows an operand); rendered flags follow; ``--json`` is appended
    last when supported.

    Args:
        entry: The validated catalog entry for the verb.
        supports_json: Whether to append ``--json``.
        arguments: The caller's validated argument object (options).
        positionals: The caller's ordered positional operands, already
            count-validated against the verb's declared arguments.
        root_dir: The server root injected via ``--target``.

    Returns:
        The full argv list ready for :func:`_run_verb`.

    Raises:
        ToolError: When an argument names a reserved or undeclared flag.
    """
    argv: list[str] = [
        sys.executable,
        "-m",
        "vaultspec_core",
        "--target",
        str(root_dir),
        *entry.verb_path,
    ]
    argv.extend(str(item) for item in positionals)
    argv.extend(_render_flags(entry.flag, arguments) if arguments else [])
    if supports_json:
        argv.append("--json")
    return argv


def _validate_positionals(entry: CatalogEntry, positionals: list[str]) -> None:
    """Reject a positional list the verb cannot accept, before any spawn.

    The values are always discrete argv items so no positional can inject a
    shell command; this guard is the catalog-validation half - it refuses
    operands a verb does not declare (a verb that takes none, or more operands
    than a non-variadic verb accepts), and it refuses any operand that begins
    with ``-``: Click would parse such a token as an option rather than an
    operand, so rejecting it before spawn keeps a caller from smuggling a
    reserved or unknown flag through the positional slot.

    Args:
        entry: The validated catalog entry for the verb.
        positionals: The caller's ordered positional operands.

    Raises:
        ToolError: When a positional begins with ``-``, the verb declares no
            positional arguments but some were supplied, or more were supplied
            than a non-variadic verb accepts.
    """
    if not positionals:
        return
    for item in positionals:
        if item.startswith("-"):
            msg = (
                f"positional {item!r} begins with '-'; positional operands "
                "must not look like options (the gateway would otherwise let "
                "a flag be smuggled through the positional slot)"
            )
            raise ToolError(msg)
    if not entry.accepts_positionals:
        msg = (
            f"verb {entry.verb!r} takes no positional arguments, "
            f"but {len(positionals)} were supplied"
        )
        raise ToolError(msg)
    ceiling = entry.max_positionals()
    if ceiling is not None and len(positionals) > ceiling:
        msg = (
            f"verb {entry.verb!r} accepts at most {ceiling} positional "
            f"argument(s), but {len(positionals)} were supplied"
        )
        raise ToolError(msg)


def _render_flags(flag_lookup: Any, arguments: dict[str, Any]) -> list[str]:
    """Render a validated argument object into discrete flag argv items.

    Each key becomes a ``--kebab-case`` flag validated against the verb's
    declared options. Value-taking options emit ``--flag value`` (a list value
    repeats the flag per item); boolean options emit a bare ``--flag`` when
    truthy and nothing when falsy. Reserved and undeclared flags are rejected
    so a caller can neither shadow the injected ``--target`` / ``--json`` nor
    smuggle an unknown token.

    Flags listed in :data:`~vaultspec_core.mcp_server.catalog.BLOCKED_FLAGS`
    are rejected even though the verb declares them: a declared flag whose
    *value* is a command to execute is screened by neither of the other two
    checks, because the name is legitimate and the value is never examined
    here.

    Args:
        flag_lookup: The entry's ``flag(name)`` resolver.
        arguments: The caller's argument object.

    Returns:
        The rendered argv fragments.

    Raises:
        ToolError: On a reserved, blocked, or undeclared flag.
    """
    rendered: list[str] = []
    for key, value in arguments.items():
        flag_name = "--" + str(key).lstrip("-").replace("_", "-")
        if flag_name in RESERVED_FLAGS:
            msg = (
                f"argument {key!r} maps to reserved flag {flag_name!r}; "
                "the gateway manages --target and --json itself"
            )
            raise ToolError(msg)
        if flag_name in BLOCKED_FLAGS:
            msg = (
                f"flag {flag_name!r} is not available through the gateway; it "
                "names a command for the CLI to execute, which is meaningful "
                "only for an invocation that has a terminal attached"
            )
            raise ToolError(msg)
        declared = flag_lookup(flag_name)
        if declared is None:
            msg = f"unknown flag {flag_name!r} for this verb"
            raise ToolError(msg)
        if declared.takes_value:
            values = cast("list[object]", value) if isinstance(value, list) else [value]
            for item in values:
                rendered.append(flag_name)
                rendered.append(str(item))
        elif value:
            rendered.append(flag_name)
    return rendered


def _parse_verb(verb: str) -> tuple[str, ...]:
    """Split a submitted verb string into a normalized path tuple."""
    return tuple(verb.split())


def _child_environment() -> dict[str, str]:
    """Build the environment for an ``invoke`` subprocess.

    The server's own environment plus one marker,
    :data:`~vaultspec_core.config.VAULTSPEC_MCP_GATEWAY_INVOCATION`, telling the child
    that it was started by a tool call rather than by a person at a terminal.
    The child refuses to launch an interactive editor when it sees the marker.

    The marker is assigned here, after copying, so a value inherited from the
    server's own environment cannot suppress it; and because a caller's only
    channels into ``invoke`` are the verb path, the argument object and the
    positionals - none of which reach this mapping - the distinction it draws
    cannot be spoofed from the outside. It fails closed: the marker's absence
    is what permits editing, and the marker is set unconditionally.

    Returns:
        The environment mapping to hand to the child process.
    """
    return child_environment((VAULTSPEC_MCP_GATEWAY_INVOCATION, "1"))


# ---------------------------------------------------------------------------
# subprocess execution
# ---------------------------------------------------------------------------


def _decode(chunks: list[bytes]) -> str:
    """Decode captured stream bytes the way ``text=True`` used to.

    Reproduces :func:`subprocess.run`'s text mode exactly: UTF-8 with
    replacement, then universal-newline translation, so a Windows child's
    ``\\r\\n`` reaches the caller as ``\\n`` and the captured text does not
    drift now that the streams arrive as raw bytes.

    Args:
        chunks: The received byte chunks in arrival order.

    Returns:
        The decoded, newline-normalized text.
    """
    text = b"".join(chunks).decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


async def _drain(stream: ByteReceiveStream | None, chunks: list[bytes]) -> None:
    """Accumulate one child stream to EOF.

    Both streams are drained concurrently by the caller, because a child that
    fills one pipe buffer while the reader waits on the other deadlocks - the
    same reason :func:`subprocess.run` reads through ``communicate()``.

    Args:
        stream: The child stream, or ``None`` when it was not piped.
        chunks: The list to append received chunks to.
    """
    if stream is None:
        return
    async for chunk in stream:
        chunks.append(chunk)


async def _reap(process: Process) -> None:
    """Stop a still-running child: terminate, grace, then kill.

    The wait is shielded because this runs from the cancellation path, where
    every unshielded ``await`` would re-raise at once and leave the child
    running.

    anyio's own context-manager exit does not cover this. Its ``aclose``
    kills only when its internal ``wait()`` is itself interrupted, which
    requires a cancel scope still actively cancelling around it. Here the
    process context manager wraps the timeout scope rather than sitting
    inside it, so by the time ``aclose`` runs the timeout has already fired
    and the cancellation has already been delivered - and ``aclose`` then
    blocks on ``wait()`` for the child's entire natural lifetime. Measured on
    anyio 4.15.1, dropping this call makes a cancelled or timed-out verb hang
    until the child exits by itself.

    Only the child itself is reaped, one level, never a tree. On Windows
    ``terminate()`` and ``kill()`` are both ``TerminateProcess`` and neither
    reaps descendants, which is accepted here: the child is
    ``sys.executable -m vaultspec_core`` directly with no ``uv`` wrapper,
    editor spawning is refused by the non-interactive environment marker, and
    the hook and sync verbs are denylisted, so the only possible grandchildren
    are short-lived git invocations that exit on their own. Job Objects are
    deliberately deferred rather than overlooked.

    Args:
        process: The child to reap; a no-op when it has already exited.
    """
    if process.returncode is not None:
        return
    with anyio.CancelScope(shield=True):
        process.terminate()
        with anyio.move_on_after(_KILL_GRACE):
            await process.wait()
            return
        process.kill()
        await process.wait()


async def _run_verb(
    argv: list[str], env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run a validated argv list as a cancellable child process.

    The subprocess boundary itself is settled architecture and unchanged here
    (the module docstring states why the long tail is subprocessed rather than
    dispatched in-process); this only changes *how* the child is run. A
    blocking :func:`subprocess.run` inside an async handler pins the event
    loop for the child's whole lifetime, so the server cannot even read a
    ``notifications/cancelled`` until the child exits. Running the child
    through anyio - the same framework the SDK scopes its cancellation to -
    makes the handler interruptible at every await.

    Cancellation and timeout share one disposition: reap the child, then
    differ only in what follows. A cancelled call re-raises and returns
    nothing, since the SDK discards a cancelled handler's result anyway; a
    timeout raises :class:`TimeoutError` for the caller to fold into the
    structured ``timeout`` payload.

    Args:
        argv: The full argv list, interpreter prefix included. Never a shell
            string.
        env: The child environment, carrying the non-interactive marker.
        timeout: The wall-clock budget in seconds for the child's output.

    Returns:
        The finished process with both streams captured as text.

    Raises:
        TimeoutError: When the child outlives *timeout*; it is reaped first.
    """
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    async with await anyio.open_process(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    ) as process:
        # The child can now be terminated out from under itself, so its pid is
        # what correlates a killed or wedged verb with what the OS saw.
        logger.info("invoke: child pid=%d", process.pid)
        try:
            with anyio.fail_after(timeout):
                async with anyio.create_task_group() as streams:
                    streams.start_soon(_drain, process.stdout, stdout_chunks)
                    streams.start_soon(_drain, process.stderr, stderr_chunks)
                returncode = await process.wait()
        except BaseException:
            await _reap(process)
            raise
    return subprocess.CompletedProcess(
        argv, returncode, _decode(stdout_chunks), _decode(stderr_chunks)
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _discover_summary(payload: object) -> str:
    """Summarise a discover result as its match count.

    Args:
        payload: The ``DiscoverResult`` the tool returned.

    Returns:
        A one-line match count.
    """
    count = getattr(payload, "count", None)
    return f"{count} verbs" if count is not None else "verb search"


def _invoke_summary(payload: object) -> str:
    """Summarise an invoke result as its verb and outcome.

    Args:
        payload: The ``InvokeResult`` the tool returned.

    Returns:
        A one-line outcome, naming the failure kind when the verb failed.
    """
    verb = getattr(payload, "verb", "?")
    if getattr(payload, "ok", False):
        return f"{verb}: ok"
    error = getattr(payload, "error", None)
    kind = getattr(error, "kind", None)
    return f"{verb}: failed ({kind})" if kind else f"{verb}: failed"


def register_gateway_tools(
    mcp: MCPServer[None], *, include_invoke: bool = True
) -> None:
    """Register the ``discover`` and ``invoke`` gateway tools on *mcp*.

    ``discover`` is read-only and idempotent: a search never mutates the vault.
    ``invoke`` is annotated destructive because the long tail includes mutating
    verbs and the tool cannot know per-call which; the host confirms
    accordingly. Both keep the copied-context isolation wrapper and declare
    structured output through their typed return models.

    Args:
        mcp: The :class:`~mcp.server.mcpserver.MCPServer` instance to decorate.
        include_invoke: Whether to register the mutation-capable ``invoke`` tool.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    @compact_result(_discover_summary)
    @_isolated_context
    async def discover(
        ctx: Context[Any, Any], query: str, limit: int = 10
    ) -> DiscoverResult:
        """Search the long-tail verb catalog and return ranked schemas.

        Ranks every cataloged verb against ``query`` across its path and
        description and returns the best matches with their full parameter
        schemas. The returned verbs are exactly those
        addressable by ``invoke`` - the static denylist is already applied.

        Args:
            ctx: The MCP request context (unused; logging routes through the
                module logger instead of the deprecated client-facing channel).
            query: The free-text search string (verb words, an intent phrase).
            limit: The maximum number of ranked verbs to return.

        Returns:
            The :class:`DiscoverResult` with ranked verbs and their schemas.

        Raises:
            ToolError: When the shipped CLI reference carries no
                command-inventory marker block, so no verb is addressable.
        """
        _ = ctx
        logger.info("discover: query=%r limit=%d", query, limit)
        catalog = _active_catalog()
        ranked = catalog.search(query, limit=limit)
        verbs = [
            VerbSchema(
                verb=entry.verb,
                description=entry.description,
                score=score,
                supports_json=entry.supports_json,
                flags=[
                    FlagSchema(
                        name=flag.name,
                        takes_value=flag.takes_value,
                        help=flag.help,
                    )
                    for flag in entry.flags
                    if flag.name not in BLOCKED_FLAGS
                ],
                arguments=[
                    ArgumentSchema(
                        name=arg.name,
                        required=arg.required,
                        variadic=arg.variadic,
                    )
                    for arg in entry.arguments
                ],
            )
            for score, entry in ranked
        ]
        return DiscoverResult(query=query, count=len(verbs), verbs=verbs)

    @compact_result(_invoke_summary)
    @_isolated_context
    async def invoke(
        ctx: Context[Any, Any],
        verb: str,
        arguments: dict[str, Any] | None = None,
        positionals: list[str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> InvokeResult:
        # The spawn contract - argv list never a shell, --target injected,
        # denylist checked before anything starts - is documented on the module
        # rather than in this docstring. It constrains the implementation, not
        # the caller, and every character here is re-sent on every turn.
        """Execute one cataloged verb. A verb that runs and fails is still a
        successful call; its exit code and stderr arrive in the error payload.

        Args:
            ctx: The MCP request context (unused; logging routes through the
                module logger instead of the deprecated client-facing channel).
            verb: The space-joined verb path, e.g. ``"vault list"``.
            arguments: The verb's flags as a mapping (``feature`` -> value);
                value-taking flags may pass a list to repeat, boolean flags
                pass ``True``. ``--target`` and ``--json`` are server-managed
                and must not be supplied.
            positionals: The verb's ordered positional operands (e.g. the
                ``TYPE`` of ``vault add``, the ``PLAN`` and ``STEP`` of
                ``vault plan step check``, the ``OLD`` and ``NEW`` of ``vault
                feature rename``), in command-line order. Validated against the
                verb's declared argument count before any spawn.
            timeout: The subprocess wall-clock budget in seconds.

        Returns:
            The :class:`InvokeResult` carrying parsed data or text, or the
            structured error payload for a verb that ran and failed.

        Raises:
            ToolError: When the verb is unknown, denied, an argument names a
                reserved or undeclared flag, the positionals do not fit the
                verb's declared arguments, or the shipped CLI reference carries
                no command-inventory marker block - surfaced as a protocol
                error before any process is spawned.
        """
        _ = ctx
        verb_path = _parse_verb(verb)
        catalog = _active_catalog()

        if catalog.is_denied(verb_path):
            msg = f"verb {verb!r} is out of scope for the gateway (denylisted)"
            raise ToolError(msg)
        entry = catalog.get(verb_path)
        if entry is None:
            msg = f"unknown verb {verb!r}; use discover to find a valid verb path"
            raise ToolError(msg)

        ordered_positionals = list(positionals or [])
        _validate_positionals(entry, ordered_positionals)

        root_dir = _get_ctx().target_dir
        argv = _build_argv(
            entry,
            entry.supports_json,
            arguments or {},
            ordered_positionals,
            root_dir,
        )
        logger.info(
            "invoke: verb=%r json=%s positionals=%d",
            verb,
            entry.supports_json,
            len(ordered_positionals),
        )

        command = ["vaultspec-core", *argv[argv.index("--target") :]]
        try:
            completed = await _run_verb(argv, _child_environment(), timeout)
        except TimeoutError:
            logger.warning("invoke: verb=%r timed out after %ss", verb, timeout)
            return InvokeResult(
                verb=entry.verb,
                ok=False,
                exit_code=-1,
                format="text",
                error=InvokeError(
                    kind="timeout",
                    exit_code=-1,
                    message=f"verb timed out after {timeout} seconds",
                ),
                command=command,
            )

        return _fold_completed(entry.verb, entry.supports_json, completed, command)

    if include_invoke:
        mcp.tool(
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=True,
                idempotent_hint=False,
                open_world_hint=False,
            ),
        )(invoke)

    _ = (discover, invoke)  # bound by the decorators; silence unused warnings


def _fold_completed(
    verb: str,
    supports_json: bool,
    completed: subprocess.CompletedProcess[str],
    command: list[str],
) -> InvokeResult:
    """Fold a finished subprocess into the structured ``invoke`` result.

    Args:
        verb: The executed verb path.
        supports_json: Whether ``--json`` was appended.
        completed: The finished process with captured streams.
        command: The interpreter-free argv preview.

    Returns:
        The populated :class:`InvokeResult`.
    """
    if completed.returncode != 0:
        return InvokeResult(
            verb=verb,
            ok=False,
            exit_code=completed.returncode,
            format="text",
            stdout=completed.stdout or None,
            error=InvokeError(
                kind="nonzero_exit",
                exit_code=completed.returncode,
                stderr=completed.stderr or "",
                message=f"verb exited with status {completed.returncode}",
            ),
            command=command,
        )

    if supports_json:
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return InvokeResult(
                verb=verb,
                ok=False,
                exit_code=0,
                format="text",
                stdout=completed.stdout,
                error=InvokeError(
                    kind="json_parse",
                    exit_code=0,
                    stderr=completed.stderr or "",
                    message=f"verb declared --json but its output did not parse: {exc}",
                ),
                command=command,
            )
        return InvokeResult(
            verb=verb,
            ok=True,
            exit_code=0,
            format="json",
            data=data,
            command=command,
        )

    return InvokeResult(
        verb=verb,
        ok=True,
        exit_code=0,
        format="text",
        stdout=completed.stdout,
        command=command,
    )
