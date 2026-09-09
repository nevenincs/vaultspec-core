"""The program surface a reference describes, captured and compared.

A generated reference describes whatever surface the tree it was rendered from
happens to have. Between two releases that is not the published surface, and
this repository's version string cannot tell them apart: ``pyproject.toml``
carries the released version until release-please's pull request bumps it, so
main declares the version PyPI serves while exposing commands that version does
not have.

This module supplies the missing half - a record of what the *published*
surface was, so the difference against the live one is computable rather than
asserted (per the ``reference-publication-contract`` ADR). Two pieces:

*Capture.* :func:`capture_surface` reads the live CLI verb tree and the live
MCP tool registry into a :class:`Surface`. The CLI walk delegates to
:func:`~vaultspec_core.cli.reference_gen.leaf_command_paths`, so the snapshot
and the rendered command inventory can never disagree about what a command is.

*Comparison.* :func:`unreleased_surface` returns the verbs and flags and tools
present live and absent from a published :class:`Surface`. That difference is
what the reference renders in place of hand-written per-command caveats: it has
no skipped state, and it empties itself when a release ships rather than
expiring.

The snapshot is JSON under ``builtins/`` so it ships in the wheel alongside the
reference it attributes, and so the publish lane has one immutable object to
verify a released distribution against.

Refresh is deliberately narrow. :func:`refresh_reason` permits a rewrite only
when the tree's version differs from the snapshot's - the release candidate
branch, where the version is already the candidate's and the tree is the one
about to be tagged. On main between releases the two versions are equal, and
rewriting there would restamp HEAD-only commands as released, which is the
exact falsehood this module exists to prevent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    import typer
    from typer._click.core import Command as ClickCommand
    from typer._click.core import Context as ClickContext

#: Schema version of the snapshot document. Bumped only when the shape changes
#: in a way a reader must branch on; the publish-lane check reads it to refuse
#: a snapshot it does not understand rather than silently comparing nothing.
SNAPSHOT_SCHEMA = 1

__all__ = [
    "SNAPSHOT_SCHEMA",
    "McpTool",
    "Surface",
    "SurfaceSnapshotError",
    "UnreleasedSurface",
    "capture_mcp_tool_details",
    "capture_surface",
    "load_published_surface",
    "project_version",
    "published_surface_path",
    "refresh_reason",
    "serialize_surface",
    "unreleased_surface",
    "write_published_surface",
]


class SurfaceSnapshotError(ValueError):
    """The published-surface snapshot is missing, unreadable, or unknown.

    Distinct from a bare :class:`ValueError` so a caller can tell a broken
    snapshot from a rendering fault and report the repair command for it.
    """


def published_surface_path() -> Path:
    """Return the filesystem path to the bundled published-surface snapshot."""
    from vaultspec_core.builtins import builtins_root

    return builtins_root() / "reference" / "published-surface.json"


def _pyproject_path() -> Path:
    from pathlib import Path as _Path

    return _Path(__file__).resolve().parents[3] / "pyproject.toml"


def project_version() -> str:
    """Return the version of the tree this process is running from.

    Read from ``pyproject.toml`` when it is present, and only from installed
    package metadata otherwise. The order matters on the release candidate
    branch: release-please bumps ``pyproject.toml`` there and nothing
    reinstalls the package, so ``__version__`` would still report the previous
    release and the snapshot would be stamped with the version it is replacing.
    """
    import tomllib

    pyproject = _pyproject_path()
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        version = data.get("project", {}).get("version")
        if isinstance(version, str) and version:
            return version

    from vaultspec_core import __version__

    return __version__


@dataclass(frozen=True)
class Surface:
    """One program surface: its CLI verbs with their flags, and its MCP tools.

    ``version`` is the version this surface belongs to. ``commands`` maps a
    full verb path (``"spec gitignore disable"``, without the executable name)
    to that verb's sorted long-form option names. ``mcp_tools`` is the sorted
    tool-name set the MCP server registers in its full, non-read-only mode.

    Every collection is sorted, because a snapshot is a set membership question
    and not a rendering: ordering churn in the command modules must not produce
    a diff in the committed artifact.
    """

    version: str
    commands: dict[str, tuple[str, ...]]
    mcp_tools: tuple[str, ...]

    def command_names(self) -> frozenset[str]:
        """Return the verb paths this surface exposes."""
        return frozenset(self.commands)


@dataclass(frozen=True)
class UnreleasedSurface:
    """What the live surface has that a published surface does not.

    ``commands`` are whole verbs absent from the release. ``flags`` maps a verb
    the release *does* have to the option names it does not, so a flag added to
    an existing command is attributed as precisely as a new command is.
    ``mcp_tools`` are tool names absent from the release.
    """

    published_version: str
    commands: tuple[str, ...]
    flags: dict[str, tuple[str, ...]]
    mcp_tools: tuple[str, ...]

    def is_empty(self) -> bool:
        """True when the live surface adds nothing to the published one."""
        return not (self.commands or self.flags or self.mcp_tools)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _long_options(command: ClickCommand, ctx: ClickContext) -> tuple[str, ...]:
    """Return the sorted long-form option names of a resolved leaf command.

    ``--help`` is dropped: Click synthesises it on every command, so it carries
    no information about the surface and would only add noise to every entry.
    """
    names: set[str] = set()
    for param in command.get_params(ctx):
        if param.param_type_name != "option":
            continue
        names.update(opt for opt in param.opts if opt.startswith("--"))
    names.discard("--help")
    return tuple(sorted(names))


def capture_cli_commands(typer_app: typer.Typer) -> dict[str, tuple[str, ...]]:
    """Return every visible leaf verb path mapped to its long-form flags."""
    from typer.main import get_command

    from vaultspec_core.cli.reference_gen import (
        leaf_command_paths,
        resolve_click_command,
    )

    root = get_command(typer_app)
    root_ctx = root.context_class(root, info_name="vaultspec-core")

    commands: dict[str, tuple[str, ...]] = {}
    for path in leaf_command_paths(typer_app, ()):
        command, ctx = resolve_click_command(root, root_ctx, path)
        commands[" ".join(path)] = _long_options(command, ctx)
    return dict(sorted(commands.items()))


@dataclass(frozen=True)
class McpTool:
    """One registered MCP tool as the reference documents it.

    ``purpose`` is the first line of the handler's own docstring and
    ``annotations`` the rendered form of its MCP hints, so the documented
    behavior of a tool has one home - the handler - rather than a second,
    hand-copied one in the handbook.
    """

    name: str
    purpose: str
    annotations: str


def _render_annotations(tool: object) -> str:
    """Render one tool's MCP hints in the handbook's own vocabulary.

    ``destructiveHint`` is unset on read-only tools, where it would be
    meaningless: a tool that writes nothing is not usefully described as
    non-destructive. Those rows say ``read-only`` instead, which is what the
    hand-written table said before this was generated.
    """
    hints = getattr(tool, "annotations", None)
    read_only = bool(getattr(hints, "read_only_hint", False))
    destructive = getattr(hints, "destructive_hint", None)
    idempotent = bool(getattr(hints, "idempotent_hint", False))

    parts = ["read-only"] if read_only else []
    if not read_only:
        parts.append("destructive" if destructive else "non-destructive")
    parts.append("idempotent" if idempotent else "not idempotent")
    return ", ".join(parts)


def capture_mcp_tool_details() -> tuple[McpTool, ...]:
    """Return every registered MCP tool, in registration order.

    The full surface is captured, not the read-only one: the read-only mode is
    a runtime restriction over the same registry, so a reference that described
    only its subset would understate what the release ships. Registration order
    is preserved here - the handbook reads as a tour, not an index - while
    :func:`capture_mcp_tools` sorts, because a snapshot is set membership.
    """
    import asyncio

    from vaultspec_core.mcp_server.app import create_server

    async def _tools() -> tuple[McpTool, ...]:
        registered = await create_server().list_tools()
        return tuple(
            McpTool(
                name=tool.name,
                purpose=_summary_paragraph(tool.description or ""),
                annotations=_render_annotations(tool),
            )
            for tool in registered
        )

    return asyncio.run(_tools())


def _summary_paragraph(description: str) -> str:
    """Return a handler docstring's summary paragraph as one flat line.

    The paragraph, not the first physical line and not the first sentence. A
    summary that wraps would be cut mid-clause by the line, and one that opens
    with a short sentence followed by its qualification - ``invoke`` does -
    would lose the qualification to the sentence split.
    """
    paragraph = description.strip().split("\n\n", 1)[0]
    return " ".join(paragraph.split())


def capture_mcp_tools() -> tuple[str, ...]:
    """Return the sorted tool names the MCP server registers."""
    return tuple(sorted(tool.name for tool in capture_mcp_tool_details()))


def capture_surface(
    typer_app: typer.Typer | None = None, version: str | None = None
) -> Surface:
    """Capture the live CLI and MCP surface, stamped with the tree's version."""
    if typer_app is None:
        from vaultspec_core.cli import app as typer_app

    return Surface(
        version=version if version is not None else project_version(),
        commands=capture_cli_commands(typer_app),
        mcp_tools=capture_mcp_tools(),
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_surface(surface: Surface) -> str:
    """Render *surface* as the committed snapshot document.

    Two-space indent, sorted keys, and a trailing newline, so the artifact is
    stable across runs and reviewable as a diff.
    """
    document = {
        "schema": SNAPSHOT_SCHEMA,
        "version": surface.version,
        "commands": {name: list(flags) for name, flags in surface.commands.items()},
        "mcp_tools": list(surface.mcp_tools),
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def deserialize_surface(text: str) -> Surface:
    """Parse a committed snapshot document into a :class:`Surface`.

    Raises:
        SurfaceSnapshotError: The document is not valid JSON, does not carry a
            schema this build understands, or is missing a required field.
    """
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SurfaceSnapshotError(f"snapshot is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SurfaceSnapshotError("snapshot is not a JSON object")
    document = cast("dict[str, object]", parsed)

    schema = document.get("schema")
    if schema != SNAPSHOT_SCHEMA:
        raise SurfaceSnapshotError(
            f"snapshot declares schema {schema!r}; this build reads {SNAPSHOT_SCHEMA}"
        )

    version = document.get("version")
    if not isinstance(version, str) or not version:
        raise SurfaceSnapshotError("snapshot carries no version")

    raw_commands = document.get("commands")
    if not isinstance(raw_commands, dict):
        raise SurfaceSnapshotError("snapshot carries no command map")

    raw_tools = document.get("mcp_tools")
    if not isinstance(raw_tools, list):
        raise SurfaceSnapshotError("snapshot carries no MCP tool list")

    commands: dict[str, tuple[str, ...]] = {}
    for name, flags in sorted(cast("dict[str, object]", raw_commands).items()):
        if not isinstance(flags, list):
            raise SurfaceSnapshotError(f"snapshot entry {name!r} carries no flag list")
        commands[name] = tuple(str(flag) for flag in cast("list[object]", flags))

    return Surface(
        version=version,
        commands=commands,
        mcp_tools=tuple(str(tool) for tool in cast("list[object]", raw_tools)),
    )


def load_published_surface(path: Path | None = None) -> Surface:
    """Read the committed published-surface snapshot.

    Raises:
        SurfaceSnapshotError: The snapshot is absent or unreadable. Absence is
            raised rather than treated as an empty surface: an empty surface
            would render every command as unreleased, which is a louder lie
            than the one this module removes.
    """
    snapshot = path or published_surface_path()
    if not snapshot.is_file():
        raise SurfaceSnapshotError(
            f"no published-surface snapshot at {snapshot}; run "
            "'vaultspec-core spec reference snapshot' on a release branch"
        )
    return deserialize_surface(snapshot.read_text(encoding="utf-8"))


def write_published_surface(surface: Surface, path: Path | None = None) -> bool:
    """Write *surface* to the snapshot path; return whether the file changed."""
    snapshot = path or published_surface_path()
    rendered = serialize_surface(surface)
    if snapshot.is_file() and snapshot.read_text(encoding="utf-8") == rendered:
        return False
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(rendered, encoding="utf-8", newline="\n")
    return True


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def unreleased_surface(live: Surface, published: Surface) -> UnreleasedSurface:
    """Return what *live* exposes and *published* does not.

    Removals are deliberately not reported. A verb present in the release and
    absent from the tree is a retirement, which the changelog and the release
    notes own; this record answers only the question a reader of the reference
    has, which is whether what they are reading is installable.
    """
    published_commands = published.command_names()

    new_commands = tuple(
        sorted(name for name in live.commands if name not in published_commands)
    )

    new_flags: dict[str, tuple[str, ...]] = {}
    for name, flags in live.commands.items():
        if name not in published_commands:
            continue
        added = tuple(sorted(set(flags) - set(published.commands[name])))
        if added:
            new_flags[name] = added

    new_tools = tuple(sorted(set(live.mcp_tools) - set(published.mcp_tools)))

    return UnreleasedSurface(
        published_version=published.version,
        commands=new_commands,
        flags=dict(sorted(new_flags.items())),
        mcp_tools=new_tools,
    )


# ---------------------------------------------------------------------------
# Refresh policy
# ---------------------------------------------------------------------------


def refresh_reason(live: Surface, published: Surface) -> str | None:
    """Return why the snapshot may be refreshed, or ``None`` when it may not.

    The snapshot records the surface of a release. It may therefore be rewritten
    only where the tree is a different release from the one recorded - the
    candidate branch, after release-please has bumped the version. Rewriting it
    on main between releases would stamp the version of the *previous* release
    onto commands that release does not contain, restamping unreleased work as
    published, which is the failure this whole contract exists to prevent.
    """
    if live.version == published.version:
        return None
    return (
        f"tree version {live.version} differs from the recorded published "
        f"version {published.version}"
    )
