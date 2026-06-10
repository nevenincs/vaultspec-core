"""Generate the derivable regions of the bundled CLI reference.

The bundled machine-facing reference at
``src/vaultspec_core/builtins/reference/cli.md`` is a hybrid of two content
classes (per the ``cli-reference-automation`` ADR): mechanically derivable
zones that this module owns and rewrites, and hand-written prose zones that it
preserves verbatim.

Generator-owned zones are delimited in the markdown by stable HTML-comment
markers::

    <!-- vaultspec:generated:begin <region-id> -->
    ...generated content...
    <!-- vaultspec:generated:end <region-id> -->

This module walks the live Typer command tree exactly as the drift guard
(:mod:`vaultspec_core.tests.cli.test_cli_reference_drift`) does -
``registered_commands`` and ``registered_groups``, descending recursively and
skipping ``hidden`` entries - and reads per-command argument metadata from the
Click command objects Typer builds. From that tree it renders the
command-inventory signature block. Everything outside the managed markers
(entry-point table, global-options narrative, sync-vocabulary section, the
curated per-command option tables, the consolidated ``vault check`` / ``vault
plan`` paragraphs, the exit-code table, and the environment-variable table) is
left untouched.

The renderer runs in two modes from one rendering path. :func:`generate` with
``check=False`` rewrites the managed regions in place; with ``check=True`` it
renders into memory, diffs against the committed file, and reports whether they
match. The CLI verb ``vaultspec-core spec reference generate`` exposes both
modes; ``--check`` is the CI and pre-commit entry point.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import click
    import typer

# Marker grammar. The region id is interpolated between the fixed prefix and
# suffix so a single regex-free string search locates each managed zone.
_MARKER_PREFIX = "<!-- vaultspec:generated:begin "
_MARKER_SUFFIX = " -->"
_END_PREFIX = "<!-- vaultspec:generated:end "


def begin_marker(region_id: str) -> str:
    """Return the opening marker line for *region_id*."""
    return f"{_MARKER_PREFIX}{region_id}{_MARKER_SUFFIX}"


def end_marker(region_id: str) -> str:
    """Return the closing marker line for *region_id*."""
    return f"{_END_PREFIX}{region_id}{_MARKER_SUFFIX}"


def bundled_reference_path() -> Path:
    """Return the filesystem path to the bundled ``reference/cli.md``."""
    from vaultspec_core.builtins import _builtins_root

    return _builtins_root() / "reference" / "cli.md"


def docs_handbook_path() -> Path:
    """Return the filesystem path to the source-tree handbook ``docs/CLI.md``.

    The handbook is a source-only artifact: it lives in the repository under
    ``docs/`` and is not shipped inside the installed wheel. The generator owns
    its command-inventory region so the two surfaces cannot drift; when the
    file is absent (an installed wheel, not a checkout) it is simply skipped by
    the registry walk.
    """
    from pathlib import Path as _Path

    return _Path(__file__).resolve().parents[3] / "docs" / "CLI.md"


# ---------------------------------------------------------------------------
# Typer / Click introspection
# ---------------------------------------------------------------------------


def _leaf_commands_in_order(
    typer_app: typer.Typer, prefix: tuple[str, ...]
) -> list[tuple[str, ...]]:
    """Return visible leaf-command paths in registration order.

    Mirrors the drift guard's tree walk: commands declared on a level come
    before its sub-groups, and ``hidden`` entries are skipped. Registration
    order (not alphabetical) is preserved so the rendered inventory matches the
    order a contributor reads the command modules in.
    """
    paths: list[tuple[str, ...]] = []
    for info in typer_app.registered_commands:
        if info.hidden:
            continue
        name = info.name
        if not name and info.callback is not None:
            name = getattr(info.callback, "__name__", None)
        if name:
            paths.append((*prefix, name))
    for group in typer_app.registered_groups:
        name = group.name
        if not name or group.hidden:
            continue
        if group.typer_instance is not None:
            paths.extend(_leaf_commands_in_order(group.typer_instance, (*prefix, name)))
    return paths


def _resolve_click_command(
    root: click.Command, root_ctx: click.Context, path: tuple[str, ...]
) -> tuple[click.Command, click.Context]:
    """Descend the Click command tree to the command at *path*."""
    import click

    command = root
    ctx = root_ctx
    for segment in path:
        assert isinstance(command, click.Group)
        sub = command.get_command(ctx, segment)
        if sub is None:
            raise KeyError(f"Click command not found for path: {' '.join(path)}")
        command = sub
        ctx = click.Context(sub, info_name=segment, parent=ctx)
    return command, ctx


def _command_signature(
    command: click.Command, ctx: click.Context, path: tuple[str, ...]
) -> str:
    """Render one leaf signature line: ``vaultspec-core <path> [OPTIONS] ARGS``.

    The ``[OPTIONS]`` token is emitted unconditionally to match the Typer usage
    line shape; positional arguments follow in declaration order, each rendered
    through Click's own ``make_metavar`` so optional arguments keep their
    ``[BRACKETS]`` and required ones stay bare.
    """
    import click

    parts = ["vaultspec-core", *path, "[OPTIONS]"]
    for param in command.get_params(ctx):
        if isinstance(param, click.Argument):
            parts.append(param.make_metavar(ctx))
    return " ".join(parts)


def collect_leaf_signatures(typer_app: typer.Typer) -> list[str]:
    """Return every visible leaf-command signature line in registration order."""
    import click
    from typer.main import get_command

    root = get_command(typer_app)
    root_ctx = click.Context(root, info_name="vaultspec-core")

    signatures: list[str] = []
    for path in _leaf_commands_in_order(typer_app, ()):
        command, ctx = _resolve_click_command(root, root_ctx, path)
        signatures.append(_command_signature(command, ctx, path))
    return signatures


# ---------------------------------------------------------------------------
# Region renderers
# ---------------------------------------------------------------------------


def render_command_inventory(typer_app: typer.Typer) -> str:
    """Render the command-inventory fenced block body (without markers).

    The body is a single ``text`` fenced block listing every leaf signature,
    surrounded by the blank lines mdformat keeps between the markers and the
    block so generated output equals the formatted committed artifact.
    """
    signatures = collect_leaf_signatures(typer_app)
    lines = ["```text", *signatures, "```"]
    return "\n".join(lines)


@dataclass(frozen=True)
class ManagedRegion:
    """A generator-owned zone delimited by begin/end markers in the reference."""

    region_id: str
    render: Callable[[typer.Typer], str]


# Registry of every managed region, in document order. Adding a sibling region
# (per-command option tables, exit-code table) later extends this tuple rather
# than rewriting the apply loop.
MANAGED_REGIONS: tuple[ManagedRegion, ...] = (
    ManagedRegion(region_id="command-inventory", render=render_command_inventory),
)


@dataclass(frozen=True)
class ManagedFile:
    """A file the generator owns, plus the regions it rewrites inside it.

    ``path_factory`` is deferred so the package/repo paths resolve at call time
    (tests never need them; an installed wheel may not ship the handbook).
    ``optional`` marks a source-only file that is skipped when absent rather
    than raising, so ``--check`` stays correct both in a checkout and in an
    installed wheel.
    """

    path_factory: Callable[[], Path]
    regions: tuple[ManagedRegion, ...]
    optional: bool = False


# Registry of every generator-owned file, in document order. The same renderer
# shape extends to sibling references (mcp.md, framework.md) by appending a
# ManagedFile here rather than touching the apply loop. The bundled reference
# and the source-tree handbook share the command-inventory region so the two
# surfaces cannot silently diverge in command set or ordering.
MANAGED_FILES: tuple[ManagedFile, ...] = (
    ManagedFile(path_factory=bundled_reference_path, regions=MANAGED_REGIONS),
    ManagedFile(
        path_factory=docs_handbook_path,
        regions=MANAGED_REGIONS,
        optional=True,
    ),
)


# ---------------------------------------------------------------------------
# Region application
# ---------------------------------------------------------------------------


class ReferenceMarkerError(ValueError):
    """Raised when a managed region's markers are missing or malformed."""


def _replace_region(text: str, region: ManagedRegion, body: str) -> str:
    """Replace the content between *region*'s markers with *body*.

    The begin and end marker lines are preserved exactly; only the content
    between them is rewritten. A single blank line separates each marker from
    the body, matching the mdformat layout, so a freshly generated file is
    byte-identical to one that has been formatted.
    """
    begin = begin_marker(region.region_id)
    end = end_marker(region.region_id)

    # Each marker must appear exactly once. A duplicated begin marker would
    # otherwise let the anchored end search bind to the wrong pair and silently
    # swallow the first region's body; a duplicated end marker is equally
    # ambiguous. Refuse to guess which copy is canonical.
    begin_count = text.count(begin)
    if begin_count > 1:
        raise ReferenceMarkerError(
            f"Duplicate begin marker for managed region {region.region_id!r} "
            f"(found {begin_count}; expected exactly one)"
        )
    end_count = text.count(end)
    if end_count > 1:
        raise ReferenceMarkerError(
            f"Duplicate end marker for managed region {region.region_id!r} "
            f"(found {end_count}; expected exactly one)"
        )

    begin_idx = text.find(begin)
    if begin_idx == -1:
        raise ReferenceMarkerError(
            f"Missing begin marker for managed region {region.region_id!r}"
        )
    end_idx = text.find(end, begin_idx)
    if end_idx == -1:
        # The anchored search (after begin) failed. Distinguish a genuinely
        # absent end marker from a misordered pair: if an unanchored search
        # finds the end marker, it exists but precedes the begin marker, which
        # is a different defect than a missing one.
        if end in text:
            raise ReferenceMarkerError(
                f"End marker precedes begin marker for region {region.region_id!r}"
            )
        raise ReferenceMarkerError(
            f"Missing end marker for managed region {region.region_id!r}"
        )

    before = text[:begin_idx] + begin
    after = end + text[end_idx + len(end) :]
    return f"{before}\n\n{body}\n\n{after}"


def render_reference(
    committed_text: str,
    typer_app: typer.Typer,
    regions: tuple[ManagedRegion, ...] = MANAGED_REGIONS,
) -> str:
    """Return *committed_text* with every managed region freshly rendered.

    Prose zones outside the markers are carried through verbatim; only the
    content between each region's markers is replaced with generator output.
    *regions* defaults to the bundled-reference region set; a caller may pass a
    file-specific region tuple from the :data:`MANAGED_FILES` registry.
    """
    text = committed_text
    for region in regions:
        text = _replace_region(text, region, region.render(typer_app))
    return text


# ---------------------------------------------------------------------------
# Generate / check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerateResult:
    """Outcome of a generate or check pass."""

    path: Path
    changed: bool
    diff: str

    @property
    def in_sync(self) -> bool:
        """True when the committed reference already equals fresh output."""
        return not self.changed


def _unified_diff(old: str, new: str, path: Path) -> str:
    rel = path.name
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


def generate(
    *,
    check: bool,
    reference_path: Path | None = None,
    typer_app: typer.Typer | None = None,
    regions: tuple[ManagedRegion, ...] = MANAGED_REGIONS,
) -> GenerateResult:
    """Render the managed regions of one generator-owned file.

    Args:
        check: When ``True`` the file is left untouched; the rendered output is
            diffed against the committed content and the diff is returned.
            When ``False`` the rendered output is written back in place when it
            differs.
        reference_path: Override the bundled reference path (tests point this
            at a fixture).
        typer_app: Override the Typer app object introspected (defaults to the
            live :data:`vaultspec_core.cli.app`).
        regions: The region tuple to rewrite; defaults to the bundled
            reference's region set.

    Returns:
        A :class:`GenerateResult` recording whether the committed file diverged
        from fresh output and the unified diff between them.
    """
    if typer_app is None:
        from vaultspec_core.cli import app as typer_app

    path = reference_path or bundled_reference_path()
    committed = path.read_text(encoding="utf-8")
    rendered = render_reference(committed, typer_app, regions)

    changed = rendered != committed
    diff = _unified_diff(committed, rendered, path) if changed else ""

    if changed and not check:
        path.write_text(rendered, encoding="utf-8", newline="\n")

    return GenerateResult(path=path, changed=changed, diff=diff)


def generate_all(
    *,
    check: bool,
    typer_app: typer.Typer | None = None,
) -> list[GenerateResult]:
    """Render every generator-owned file in the :data:`MANAGED_FILES` registry.

    Each registry entry is rendered through :func:`generate`. Optional files
    (the source-only handbook) that are absent on disk are skipped, so a
    ``--check`` run in an installed wheel covers only the files it ships while a
    checkout covers both the bundled reference and ``docs/CLI.md``.

    Args:
        check: Forwarded to :func:`generate`; ``True`` leaves files untouched
            and only diffs, ``False`` rewrites drifted regions in place.
        typer_app: Override the Typer app object introspected (defaults to the
            live :data:`vaultspec_core.cli.app`).

    Returns:
        One :class:`GenerateResult` per processed file, in registry order.
    """
    if typer_app is None:
        from vaultspec_core.cli import app as typer_app

    results: list[GenerateResult] = []
    for managed in MANAGED_FILES:
        path = managed.path_factory()
        if managed.optional and not path.is_file():
            continue
        results.append(
            generate(
                check=check,
                reference_path=path,
                typer_app=typer_app,
                regions=managed.regions,
            )
        )
    return results
