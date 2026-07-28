"""Scaffold the core and provider directory structures on disk.

Covers only the directory/file creation (or dry-run preview) primitives that
``install``/``init`` compose into a full provisioning run: the
``.vaultspec/``/``.vault/`` skeleton and each enrolled provider's rules,
skills, agents, workflows, and config file locations.
"""

from __future__ import annotations

from pathlib import Path

from . import types as _t
from .enums import ProviderCapability, Tool
from .helpers import atomic_write, ensure_dir
from .provider_registry import rel


def scaffold_core(target: Path, *, dry_run: bool = False) -> list[tuple[str, str]]:
    """Scaffold the ``.vaultspec/`` and ``.vault/`` directory structures.

    Args:
        target: Workspace root directory.
        dry_run: When ``True``, returns the manifest without creating anything.

    Returns:
        List of ``(relative_path, label)`` tuples for all directories created
        or that would be created.
    """
    fw_dir = target / ".vaultspec"
    vault_dir = target / ".vault"
    created: list[tuple[str, str]] = []

    # Ensure the framework root exists unconditionally before builtins
    # discovery.  Resources are seeded directly under .vaultspec/ (no
    # intermediate rules/ wrapper), so the framework root must exist first.
    if not dry_run:
        ensure_dir(fw_dir)
    created.append((rel(target, fw_dir), "core (.vaultspec)"))

    # Dynamically discover resource categories from the builtins package
    # so that new categories (e.g. hooks) are scaffolded automatically.
    # Resolved directly through importlib.resources (the same public API
    # the builtins package's own root helper wraps) so this module never
    # reaches into that package's private surface.
    from importlib import resources

    builtins_root = Path(str(resources.files("vaultspec_core.builtins")))
    subdirs = sorted(
        d.name
        for d in builtins_root.iterdir()
        if d.is_dir() and d.name not in ("__pycache__",)
    )
    for subdir in subdirs:
        d = fw_dir / subdir
        if not dry_run:
            ensure_dir(d)
        created.append((rel(target, d), "core (.vaultspec)"))

    from vaultspec_core.vaultcore.models import DocType

    for subdir in sorted(dt.value for dt in DocType):
        d = vault_dir / subdir
        if not dry_run:
            ensure_dir(d)
        created.append((rel(target, d), "vault (.vault)"))

    return created


def _is_skill_dir(path: Path) -> bool:
    """Whether ``path`` is a skill directory (holds a ``SKILL.md``)."""
    return path.is_dir() and (path / "SKILL.md").exists()


def _provider_dir_preview_names(src_dir: Path | None, *, is_skill: bool) -> list[str]:
    """List the source file/dir names a dry-run preview would deploy.

    Returns an empty list when ``src_dir`` is absent (a true fresh install
    before the builtins are seeded), which tells the caller to fall back to
    a single directory-line entry.
    """
    if src_dir is None or not src_dir.is_dir():
        return []
    if is_skill:
        return sorted(p.name for p in src_dir.iterdir() if _is_skill_dir(p))
    return sorted(p.name for p in src_dir.glob("*.md"))


def _dir_or_file_rels(
    target: Path,
    dest_dir: Path,
    src_dir: Path | None,
    *,
    dry_run: bool,
    is_skill: bool = False,
) -> list[str]:
    """Relative paths to record for a provider directory.

    The dry-run preview lists the individual files sync would deploy, so it
    matches the per-file granularity of ``sync --dry-run`` instead of
    understating provider work as a single directory line. Real install only
    needs the directory created; file content is deployed by the subsequent
    sync pass. Sources are read read-only (no flattening side effect).
    """
    names = _provider_dir_preview_names(src_dir, is_skill=is_skill) if dry_run else []
    if not names:
        return [rel(target, dest_dir)]
    return [rel(target, dest_dir / name) for name in names]


def _ensure_dir_unless_dry_run(path: Path, *, dry_run: bool) -> None:
    if not dry_run:
        ensure_dir(path)


def _scaffold_provider_subdir(
    target: Path,
    dest_dir: Path,
    src_dir: Path | None,
    *,
    dry_run: bool,
    is_skill: bool = False,
) -> list[str]:
    """Ensure ``dest_dir`` exists (unless dry-run) and list rels to record."""
    _ensure_dir_unless_dry_run(dest_dir, dry_run=dry_run)
    return _dir_or_file_rels(
        target, dest_dir, src_dir, dry_run=dry_run, is_skill=is_skill
    )


def _ensure_plain_config_file(path: Path, *, dry_run: bool) -> None:
    """Create an empty config file (and its parent dir) if it is missing."""
    if dry_run or path.exists():
        return
    ensure_dir(path.parent)
    atomic_write(path, "")


def _ensure_native_config_file(path: Path, *, dry_run: bool) -> None:
    """Ensure a native config file's parent dir exists; seed it if missing."""
    if dry_run:
        return
    ensure_dir(path.parent)
    if not path.exists():
        atomic_write(path, "")


def scaffold_provider(
    target: Path, tool: Tool, *, dry_run: bool = False
) -> list[tuple[str, str]]:
    """Scaffold directories for a single provider.

    Uses its :class:`~vaultspec_core.core.types.ToolConfig`.

    Args:
        target: Workspace root directory.
        tool: :class:`~vaultspec_core.core.enums.Tool` to scaffold.
        dry_run: When ``True``, returns the manifest without creating anything.

    Returns:
        Deduplicated list of ``(relative_path, label)`` tuples, one per
        directory or file created (or that would be created).
    """
    ctx = _t.get_context()
    cfg = ctx.tool_configs.get(tool)
    if cfg is None:
        return []

    created: list[tuple[str, str]] = []
    caps = cfg.capabilities
    label = tool.value
    seen_rels: set[str] = set()

    def _add(rel_path: str, sublabel: str) -> None:
        if rel_path not in seen_rels:
            seen_rels.add(rel_path)
            created.append((rel_path, f"{label} ({sublabel})"))

    if ProviderCapability.RULES in caps and cfg.rules_dir:
        for rel_path in _scaffold_provider_subdir(
            target, cfg.rules_dir, ctx.rules_src_dir, dry_run=dry_run
        ):
            _add(rel_path, "rules")

    if ProviderCapability.SKILLS in caps and cfg.skills_dir:
        for rel_path in _scaffold_provider_subdir(
            target, cfg.skills_dir, ctx.skills_src_dir, dry_run=dry_run, is_skill=True
        ):
            _add(rel_path, "skills")

    if ProviderCapability.AGENTS in caps and cfg.agents_dir:
        for rel_path in _scaffold_provider_subdir(
            target, cfg.agents_dir, ctx.agents_src_dir, dry_run=dry_run
        ):
            _add(rel_path, "agents")

    if ProviderCapability.WORKFLOWS in caps and cfg.workflows_dir:
        _ensure_dir_unless_dry_run(cfg.workflows_dir, dry_run=dry_run)
        _add(rel(target, cfg.workflows_dir), "workflows")

    if cfg.config_file:
        _ensure_plain_config_file(cfg.config_file, dry_run=dry_run)
        _add(rel(target, cfg.config_file), "config")

    if cfg.rule_ref_config_file:
        _add(rel(target, cfg.rule_ref_config_file), "config")

    if cfg.native_config_file:
        _ensure_native_config_file(cfg.native_config_file, dry_run=dry_run)
        _add(rel(target, cfg.native_config_file), "config")

    return created


#: Backward-compatible aliases for external callers still importing the
#: previously private names.
_scaffold_core = scaffold_core
_scaffold_provider = scaffold_provider
