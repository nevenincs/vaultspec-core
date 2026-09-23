"""Single owner of the prek/pre-commit hook boundary invariant.

When a workspace carries ``prek.toml``, prek resolves hooks from it
exclusively and silently ignores a co-present ``.pre-commit-config.yaml``
(verified against prek 0.4.10). vaultspec-core therefore treats
``prek.toml`` presence as the operator opting out of managed
``.pre-commit-config.yaml`` scaffolding.

Historically that boundary was expressed as bare ``prek.toml`` existence
checks scattered across the scaffold, the diagnosis collector, and the
uninstall path, none of which read the file's contents - so a workspace
that had correctly transplanted the canonical hooks into ``prek.toml``
was indistinguishable from one with an empty ``prek.toml`` and no hooks
anywhere. This module is the one place that answers both questions:

- does ``prek.toml`` exist (prek owns the boundary), and
- does it already carry the canonical vaultspec hooks.

All boundary decisions route through :func:`collect_prek_boundary`.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .enums import InstallMode

logger = logging.getLogger(__name__)

#: Filename of prek's native configuration at the workspace root.
PREK_CONFIG_NAME = "prek.toml"

#: The YAML hook-config filenames prek reads, in its discovery order. prek
#: stops at the first file present (after ``prek.toml``) and only warns about
#: the rest, so core manages whichever of these prek would actually run.
PRECOMMIT_CONFIG_NAMES: tuple[str, ...] = (
    ".pre-commit-config.yaml",
    ".pre-commit-config.yml",
)


def precommit_config_path(target: Path) -> Path:
    """Return the YAML hook config prek would read at *target*.

    The first of :data:`PRECOMMIT_CONFIG_NAMES` that exists wins, matching
    prek's discovery order; with neither present the ``.yaml`` spelling is the
    one a scaffold creates.

    Args:
        target: Workspace root directory.

    Returns:
        The path of the effective YAML config, which may not exist.
    """
    for name in PRECOMMIT_CONFIG_NAMES:
        candidate = target / name
        if candidate.exists():
            return candidate
    return target / PRECOMMIT_CONFIG_NAMES[0]


def existing_precommit_configs(target: Path) -> list[Path]:
    """Return every YAML hook config present at *target*, in discovery order.

    Args:
        target: Workspace root directory.

    Returns:
        The existing config paths; empty when there is none.
    """
    return [
        target / name for name in PRECOMMIT_CONFIG_NAMES if (target / name).exists()
    ]


@dataclass(frozen=True)
class PrekBoundaryState:
    """Observed state of the prek side of the hook boundary.

    Attributes:
        config_exists: ``prek.toml`` exists at the workspace root.
        parse_error: ``prek.toml`` exists but could not be parsed as TOML
            (or read at all). A workspace in this state is treated
            conservatively as hooks-absent: an unreadable config is never
            reported as healthy.
        hook_ids_present: Canonical vaultspec hook IDs found in the local
            repos of ``prek.toml``.
        entries_canonical: Every canonical hook found carries the exact
            mode-resolved canonical entry. Informational: the boundary
            treats ID presence as "hooks live here" because ``prek.toml``
            is operator-owned and a customised entry is not a stranded
            hook.
    """

    config_exists: bool
    parse_error: bool = False
    hook_ids_present: frozenset[str] = field(default_factory=frozenset)
    entries_canonical: bool = False

    @property
    def owns_boundary(self) -> bool:
        """Whether prek owns the hook boundary for this workspace."""
        return self.config_exists

    @property
    def hooks_present(self) -> bool:
        """Whether the full canonical hook set is present in ``prek.toml``."""
        from .commands import CANONICAL_HOOK_IDS

        return self.hook_ids_present == CANONICAL_HOOK_IDS


def _local_hooks(data: dict[str, object]) -> list[dict[str, object]]:
    """Extract hook tables from every ``repo = "local"`` repos entry."""
    raw_repos = data.get("repos", [])
    if not isinstance(raw_repos, list):
        return []
    repos = cast("list[object]", raw_repos)
    hooks: list[dict[str, object]] = []
    for raw_repo in repos:
        if not isinstance(raw_repo, dict):
            continue
        repo = cast("dict[str, object]", raw_repo)
        if repo.get("repo") != "local":
            continue
        raw_entries = repo.get("hooks", [])
        if isinstance(raw_entries, list):
            entries = cast("list[object]", raw_entries)
            hooks.extend(
                cast("dict[str, object]", h) for h in entries if isinstance(h, dict)
            )
    return hooks


def collect_prek_boundary(
    target: Path, *, mode: InstallMode | None = None
) -> PrekBoundaryState:
    """Assess the prek boundary for *target*.

    Reads ``prek.toml`` (when present) and checks its local repos for the
    canonical vaultspec hook IDs, comparing entries against the shape the
    workspace's resolved provisioning mode renders. An unparseable or
    unreadable ``prek.toml`` is reported with :attr:`PrekBoundaryState.parse_error`
    set and no hooks found - conservative, never healthy.

    Args:
        target: Workspace root directory.
        mode: Provisioning mode to resolve canonical entries for. When
            ``None`` it is resolved from the committed workspace
            declaration via
            :func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`.

    Returns:
        The observed :class:`PrekBoundaryState`.
    """
    from .commands import CANONICAL_HOOK_IDS, canonical_hook_entries_for_mode
    from .workspace_mode import resolve_render_mode

    config_path = target / PREK_CONFIG_NAME
    if not config_path.exists():
        return PrekBoundaryState(config_exists=False)

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", config_path, exc)
        return PrekBoundaryState(config_exists=True, parse_error=True)

    hooks = _local_hooks(data)
    found = frozenset(
        str(h.get("id")) for h in hooks if h.get("id") in CANONICAL_HOOK_IDS
    )

    if mode is None:
        mode = resolve_render_mode(target)
    expected_entries = canonical_hook_entries_for_mode(mode)
    entries_canonical = bool(found) and all(
        str(h.get("entry", "")) == expected_entries.get(str(h.get("id")), "")
        for h in hooks
        if h.get("id") in CANONICAL_HOOK_IDS
    )

    return PrekBoundaryState(
        config_exists=True,
        hook_ids_present=found,
        entries_canonical=entries_canonical,
    )


# ---------------------------------------------------------------------------
# Assisted migration: render canonical hooks into prek.toml
# ---------------------------------------------------------------------------

#: Delimiters of the vaultspec-managed hook block inside ``prek.toml``.
#: Mirrors the managed-block convention used for ``.gitignore`` /
#: ``.gitattributes``: everything between the markers is owned by
#: vaultspec-core; everything outside is operator-authored and never
#: touched. Rendering a delimited text block instead of round-tripping the
#: whole file is deliberate - it preserves operator comments and formatting
#: byte-for-byte, the fidelity a full parse-and-re-emit cycle cannot
#: guarantee.
MARKER_BEGIN = "# >>> vaultspec-managed hooks (do not edit this block) >>>"
MARKER_END = "# <<< vaultspec-managed hooks <<<"


def _toml_string(value: str) -> str:
    """Render *value* as a TOML basic string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_value(value: object) -> str:
    """Render a hook-field value as a TOML literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        items = cast("list[object]", value)
        return "[" + ", ".join(_toml_value(v) for v in items) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def render_prek_hook_block(mode: InstallMode) -> str:
    """Render the canonical vaultspec hook set as a managed ``prek.toml`` block.

    Emits one ``[[repos]]`` local repo followed by one ``[[repos.hooks]]``
    array-of-tables entry per canonical hook, in scaffold order, in the
    shape validated against prek 0.4.10 (``prek validate-config`` accepts
    ``id``/``name``/``entry``/``types``/``always_run``/``language``/
    ``pass_filenames`` verbatim). The block is self-contained, so appending
    it at end of file is valid TOML regardless of the operator's own
    content.

    Args:
        mode: Provisioning mode whose canonical entry prefix the hooks are
            rendered with.

    Returns:
        The delimited block, terminated with a newline.
    """
    from .commands import canonical_precommit_hooks_for_mode

    lines: list[str] = [MARKER_BEGIN, "[[repos]]", 'repo = "local"']
    for hook in canonical_precommit_hooks_for_mode(mode):
        lines.append("")
        lines.append("[[repos.hooks]]")
        lines.append(f"id = {_toml_string(str(hook['id']))}")
        for key, value in hook.items():
            if key != "id":
                lines.append(f"{key} = {_toml_value(value)}")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class PrekMigrationResult:
    """Outcome of :func:`migrate_hooks_to_prek`.

    Attributes:
        status: One of ``migrated`` (block written), ``unchanged``
            (canonical hooks already present, byte-for-byte no-op),
            ``declined`` (the workspace declaration refuses the hooks;
            nothing transplanted),
            ``no_prek_config`` (``prek.toml`` absent; nothing to migrate
            into), ``unparseable`` (``prek.toml`` is not valid TOML;
            refusing to append to a broken file), or ``conflicting``
            (some canonical hook IDs exist outside the managed block;
            refusing to duplicate or overwrite operator-authored hooks).
        detail: Human-readable elaboration for the CLI surface.
        yaml_removed: The superseded YAML hook config (``.yaml`` or ``.yml``) was
            deleted as part of this run.
    """

    status: str
    detail: str = ""
    yaml_removed: bool = False


def _block_carries_retired_hook(raw: str) -> bool:
    """Whether the managed block in *raw* still renders a retired hook ID.

    Only the managed block is inspected: a retired ID the operator wrote
    outside the markers is theirs, and migration never edits outside them.
    """
    from .precommit import RETIRED_HOOK_IDS

    lines = raw.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == MARKER_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == MARKER_END]
    if not (begins and ends and begins[0] < ends[0]):
        return False
    block = lines[begins[0] + 1 : ends[0]]
    rendered_ids = {f"id = {_toml_string(hook_id)}" for hook_id in RETIRED_HOOK_IDS}
    return any(line.strip() in rendered_ids for line in block)


def _replace_or_append_block(raw: str, block: str) -> str:
    """Substitute the managed block in *raw*, or append it."""
    lines = raw.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == MARKER_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == MARKER_END]
    if begins and ends and begins[0] < ends[0]:
        head = lines[: begins[0]]
        tail = lines[ends[0] + 1 :]
        body = block.splitlines()
        new_lines = [*head, *body, *tail]
        rendered = "\n".join(new_lines)
        if not rendered.endswith("\n"):
            rendered += "\n"
        return rendered
    if raw and not raw.endswith("\n"):
        raw += "\n"
    separator = "\n" if raw.strip() else ""
    return raw + separator + block


def migrate_hooks_to_prek(
    target: Path,
    *,
    mode: InstallMode | None = None,
    dry_run: bool = False,
    remove_yaml: bool = False,
) -> PrekMigrationResult:
    """Transplant the canonical vaultspec hooks into ``prek.toml``.

    Explicitly operator-invoked; never runs as part of install or sync.
    Idempotent: when the full canonical hook set is already present the
    file is left byte-for-byte untouched, unless the managed block still
    renders a hook vaultspec-core has since retired, in which case the block
    is re-rendered without it. The managed block is replaced in
    place when its markers exist, appended otherwise; operator-authored
    TOML outside the markers is never parsed for writing, only read for
    the boundary assessment.

    A workspace whose committed declaration sets ``hooks.pre_commit`` to
    ``false`` has refused the hooks, so nothing is transplanted and the
    status is ``declined``. ``remove_yaml`` still deletes any leftover YAML
    hook config in that state: the declaration already says the file is
    unwanted, and the operator asked for the removal.

    Args:
        target: Workspace root directory.
        mode: Provisioning mode to render entries for; resolved from the
            workspace declaration when ``None``.
        dry_run: Report the outcome without writing anything.
        remove_yaml: Also delete every superseded YAML hook config
            (``.pre-commit-config.yaml`` and ``.pre-commit-config.yml``)
            once the canonical hooks are verifiably present in
            ``prek.toml``, or when the workspace declined the hooks.
            Deletion is refused in every other state; prek silently ignores
            the YAML, so leaving it is safe and removing it is a tidiness
            action, never a repair.

    Returns:
        A :class:`PrekMigrationResult` describing what happened.
    """
    from .helpers import atomic_write
    from .workspace_mode import read_hooks_declaration, resolve_render_mode

    config_path = target / PREK_CONFIG_NAME

    if not read_hooks_declaration(target).pre_commit:
        detail = (
            "the workspace declaration sets hooks.pre_commit to false; no hooks "
            "transplanted (run 'vaultspec-core spec precommit enable' to "
            "restore them)"
        )
        leftovers = existing_precommit_configs(target)
        if remove_yaml and leftovers:
            if not dry_run:
                for leftover in leftovers:
                    leftover.unlink()
            names = ", ".join(p.name for p in leftovers)
            return PrekMigrationResult(
                status="declined",
                detail=f"{detail}; removed leftover {names}",
                yaml_removed=True,
            )
        return PrekMigrationResult(status="declined", detail=detail)

    if mode is None:
        mode = resolve_render_mode(target)

    boundary = collect_prek_boundary(target, mode=mode)
    if not boundary.config_exists:
        return PrekMigrationResult(
            status="no_prek_config",
            detail=(
                "prek.toml not found; this workspace uses managed "
                ".pre-commit-config.yaml scaffolding (run sync instead)"
            ),
        )
    if boundary.parse_error:
        return PrekMigrationResult(
            status="unparseable",
            detail="prek.toml is not valid TOML; fix it before migrating",
        )

    raw = config_path.read_text(encoding="utf-8")
    if boundary.hooks_present and _block_carries_retired_hook(raw):
        rendered = _replace_or_append_block(raw, render_prek_hook_block(mode))
        if not dry_run:
            atomic_write(config_path, rendered)
        result = PrekMigrationResult(
            status="migrated",
            detail="removed retired hooks from the managed block in prek.toml",
        )
    elif boundary.hooks_present:
        result = PrekMigrationResult(
            status="unchanged",
            detail="canonical hooks already present in prek.toml",
        )
    else:
        has_block = any(line.strip() == MARKER_BEGIN for line in raw.splitlines())
        if boundary.hook_ids_present and not has_block:
            return PrekMigrationResult(
                status="conflicting",
                detail=(
                    "prek.toml carries some vaultspec hook IDs outside the "
                    "managed block; complete or remove them manually "
                    f"(found: {', '.join(sorted(boundary.hook_ids_present))})"
                ),
            )
        rendered = _replace_or_append_block(raw, render_prek_hook_block(mode))
        if not dry_run:
            atomic_write(config_path, rendered)
        result = PrekMigrationResult(
            status="migrated",
            detail="canonical hooks transplanted into prek.toml",
        )

    # Every early return above (missing, unparseable, or conflicting
    # prek.toml) has already refused; reaching here means the canonical
    # hooks are present - or, on this run, just became present - in
    # prek.toml. Re-assess from disk before the destructive step as a
    # final guard against a concurrent rewrite.
    superseded = existing_precommit_configs(target)
    if (
        remove_yaml
        and superseded
        and (dry_run or collect_prek_boundary(target, mode=mode).hooks_present)
    ):
        if not dry_run:
            for config in superseded:
                config.unlink()
        names = ", ".join(p.name for p in superseded)
        result = PrekMigrationResult(
            status=result.status,
            detail=f"{result.detail}; removed superseded {names}",
            yaml_removed=True,
        )
    return result
