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

Both handlers keep the copied-context isolation wrapper, and both declare
structured output through typed Pydantic return models.
"""

from __future__ import annotations

import functools
import json
import logging
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ...core.types import get_context as _get_ctx
from ..catalog import RESERVED_FLAGS, CatalogEntry, CommandCatalog, build_catalog
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

__all__ = ["register_gateway_tools"]

#: Default wall-clock budget for a single ``invoke`` subprocess. The long tail
#: is low-frequency by definition, so a generous ceiling covers Python startup
#: plus the verb's own work without letting a wedged verb hang the handler.
_DEFAULT_TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# discover output models
# ---------------------------------------------------------------------------


class FlagSchema(BaseModel):
    """One declared option of a discovered verb.

    Attributes:
        name: The canonical long-form flag, e.g. ``--feature``.
        takes_value: Whether the option consumes a following value.
        help: The option's help text.
    """

    name: str
    takes_value: bool
    help: str = ""


class ArgumentSchema(BaseModel):
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


class VerbSchema(BaseModel):
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


class DiscoverResult(BaseModel):
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


class InvokeError(BaseModel):
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


class InvokeResult(BaseModel):
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
        The full argv list ready for :func:`subprocess.run`.

    Raises:
        ValueError: When an argument names a reserved or undeclared flag.
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
        ValueError: When a positional begins with ``-``, the verb declares no
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
            raise ValueError(msg)
    if not entry.accepts_positionals:
        msg = (
            f"verb {entry.verb!r} takes no positional arguments, "
            f"but {len(positionals)} were supplied"
        )
        raise ValueError(msg)
    ceiling = entry.max_positionals()
    if ceiling is not None and len(positionals) > ceiling:
        msg = (
            f"verb {entry.verb!r} accepts at most {ceiling} positional "
            f"argument(s), but {len(positionals)} were supplied"
        )
        raise ValueError(msg)


def _render_flags(flag_lookup: Any, arguments: dict[str, Any]) -> list[str]:
    """Render a validated argument object into discrete flag argv items.

    Each key becomes a ``--kebab-case`` flag validated against the verb's
    declared options. Value-taking options emit ``--flag value`` (a list value
    repeats the flag per item); boolean options emit a bare ``--flag`` when
    truthy and nothing when falsy. Reserved and undeclared flags are rejected
    so a caller can neither shadow the injected ``--target`` / ``--json`` nor
    smuggle an unknown token.

    Args:
        flag_lookup: The entry's ``flag(name)`` resolver.
        arguments: The caller's argument object.

    Returns:
        The rendered argv fragments.

    Raises:
        ValueError: On a reserved or undeclared flag.
    """
    rendered: list[str] = []
    for key, value in arguments.items():
        flag_name = "--" + str(key).lstrip("-").replace("_", "-")
        if flag_name in RESERVED_FLAGS:
            msg = (
                f"argument {key!r} maps to reserved flag {flag_name!r}; "
                "the gateway manages --target and --json itself"
            )
            raise ValueError(msg)
        declared = flag_lookup(flag_name)
        if declared is None:
            msg = f"unknown flag {flag_name!r} for this verb"
            raise ValueError(msg)
        if declared.takes_value:
            values = value if isinstance(value, list) else [value]
            for item in values:
                rendered.append(flag_name)
                rendered.append(str(item))
        elif value:
            rendered.append(flag_name)
    return rendered


def _parse_verb(verb: str) -> tuple[str, ...]:
    """Split a submitted verb string into a normalized path tuple."""
    return tuple(verb.split())


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_gateway_tools(mcp: FastMCP) -> None:
    """Register the ``discover`` and ``invoke`` gateway tools on *mcp*.

    ``discover`` is read-only and idempotent: a search never mutates the vault.
    ``invoke`` is annotated destructive because the long tail includes mutating
    verbs and the tool cannot know per-call which; the host confirms
    accordingly. Both keep the copied-context isolation wrapper and declare
    structured output through their typed return models.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def discover(ctx: Context, query: str, limit: int = 10) -> DiscoverResult:
        """Search the long-tail verb catalog and return ranked schemas.

        Ranks every cataloged verb against ``query`` across its path and
        description and returns the best matches with their full parameter
        schemas, so a verb's schema enters context only when the agent
        deliberately fetches it. The returned verbs are exactly those
        addressable by ``invoke`` - the static denylist is already applied.

        Args:
            ctx: The MCP request context.
            query: The free-text search string (verb words, an intent phrase).
            limit: The maximum number of ranked verbs to return.

        Returns:
            The :class:`DiscoverResult` with ranked verbs and their schemas.
        """
        await ctx.info(f"discover: query={query!r} limit={limit}")
        catalog = _load_catalog(_reference_path())
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

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def invoke(
        ctx: Context,
        verb: str,
        arguments: dict[str, Any] | None = None,
        positionals: list[str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> InvokeResult:
        """Execute one cataloged long-tail verb against the installed binary.

        Validates ``verb`` against the parsed catalog and the static denylist
        before anything spawns, then runs the installed ``vaultspec-core``
        binary as an argv list (never a shell) with ``--target`` injected and
        ``--json`` appended where the verb supports it. Returns parsed JSON on a
        clean exit, captured stdout otherwise; a non-zero exit folds stderr into
        a structured error payload while remaining a successful call.

        Args:
            ctx: The MCP request context.
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
            ValueError: When the verb is unknown, denied, an argument names a
                reserved or undeclared flag, or the positionals do not fit the
                verb's declared arguments - surfaced as a protocol error before
                any process is spawned.
        """
        verb_path = _parse_verb(verb)
        catalog = _load_catalog(_reference_path())

        if catalog.is_denied(verb_path):
            msg = f"verb {verb!r} is out of scope for the gateway (denylisted)"
            raise ValueError(msg)
        entry = catalog.get(verb_path)
        if entry is None:
            msg = f"unknown verb {verb!r}; use discover to find a valid verb path"
            raise ValueError(msg)

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
        await ctx.info(
            f"invoke: verb={verb!r} json={entry.supports_json} "
            f"positionals={len(ordered_positionals)}"
        )

        command = ["vaultspec-core", *argv[argv.index("--target") :]]
        try:
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            await ctx.warning(f"invoke: verb={verb!r} timed out after {timeout}s")
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

    _ = (discover, invoke)  # bound by the decorator; silence unused warnings


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
