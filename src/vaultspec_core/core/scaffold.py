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
from .provider_registry import _rel


def _scaffold_core(target: Path, *, dry_run: bool = False) -> list[tuple[str, str]]:
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
    created.append((_rel(target, fw_dir), "core (.vaultspec)"))

    # Dynamically discover resource categories from the builtins package
    # so that new categories (e.g. hooks) are scaffolded automatically.
    from vaultspec_core.builtins import _builtins_root

    builtins_root = _builtins_root()
    subdirs = sorted(
        d.name
        for d in builtins_root.iterdir()
        if d.is_dir() and d.name not in ("__pycache__",)
    )
    for subdir in subdirs:
        d = fw_dir / subdir
        if not dry_run:
            ensure_dir(d)
        created.append((_rel(target, d), "core (.vaultspec)"))

    from vaultspec_core.vaultcore.models import DocType

    for subdir in sorted(dt.value for dt in DocType):
        d = vault_dir / subdir
        if not dry_run:
            ensure_dir(d)
        created.append((_rel(target, d), "vault (.vault)"))

    return created


def _scaffold_provider(
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

    def _add(rel: str, sublabel: str) -> None:
        if rel not in seen_rels:
            seen_rels.add(rel)
            created.append((rel, f"{label} ({sublabel})"))

    def _add_dir_or_files(
        dest_dir: Path, sublabel: str, src_dir: Path | None, *, is_skill: bool = False
    ) -> None:
        # The dry-run preview lists the individual files sync would deploy, so it
        # matches the per-file granularity of ``sync --dry-run`` instead of
        # understating provider work as a single directory line. Real install
        # only needs the directory created; file content is deployed by the
        # subsequent sync pass. Sources are read read-only (no flattening side
        # effect). When sources are absent (a true fresh install before the
        # builtins are seeded) the directory line is the honest preview.
        names: list[str] = []
        if dry_run and src_dir is not None and src_dir.is_dir():
            if is_skill:
                names = sorted(
                    p.name
                    for p in src_dir.iterdir()
                    if p.is_dir() and (p / "SKILL.md").exists()
                )
            else:
                names = sorted(p.name for p in src_dir.glob("*.md"))
        if names:
            for name in names:
                _add(_rel(target, dest_dir / name), sublabel)
        else:
            _add(_rel(target, dest_dir), sublabel)

    if ProviderCapability.RULES in caps and cfg.rules_dir:
        if not dry_run:
            ensure_dir(cfg.rules_dir)
        _add_dir_or_files(cfg.rules_dir, "rules", ctx.rules_src_dir)

    if ProviderCapability.SKILLS in caps and cfg.skills_dir:
        if not dry_run:
            ensure_dir(cfg.skills_dir)
        _add_dir_or_files(cfg.skills_dir, "skills", ctx.skills_src_dir, is_skill=True)

    if ProviderCapability.AGENTS in caps and cfg.agents_dir:
        if not dry_run:
            ensure_dir(cfg.agents_dir)
        _add_dir_or_files(cfg.agents_dir, "agents", ctx.agents_src_dir)

    if ProviderCapability.WORKFLOWS in caps and cfg.workflows_dir:
        if not dry_run:
            ensure_dir(cfg.workflows_dir)
        _add(_rel(target, cfg.workflows_dir), "workflows")

    if cfg.config_file:
        if not dry_run and not cfg.config_file.exists():
            ensure_dir(cfg.config_file.parent)
            atomic_write(cfg.config_file, "")
        _add(_rel(target, cfg.config_file), "config")

    if cfg.rule_ref_config_file:
        _add(_rel(target, cfg.rule_ref_config_file), "config")

    if cfg.native_config_file:
        if not dry_run:
            ensure_dir(cfg.native_config_file.parent)
            if not cfg.native_config_file.exists():
                atomic_write(cfg.native_config_file, "")
        _add(_rel(target, cfg.native_config_file), "config")

    return created
