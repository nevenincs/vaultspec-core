"""Implement the top-level operational commands mounted into the root CLI.

This module contains the business logic behind workspace initialization,
install, uninstall, and sync. It sits above the lower-level resource-management
modules and provides the user-facing command behaviors that do not belong
to a dedicated nested Typer namespace.
"""

from __future__ import annotations

import contextvars
import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from . import types as _t
from .enums import InstallMode, ManagedState, PrecommitHook, ProviderCapability, Tool
from .exceptions import (
    ProviderError,
    ProviderNotInstalledError,
    VaultSpecError,
    WorkspaceNotInitializedError,
)
from .gitattributes import ensure_gitattributes_block
from .gitattributes import has_valid_block as _ga_has_valid_block
from .gitignore import (
    _collect_provider_artifacts,
    _find_markers,
    ensure_gitignore_block,
    get_recommended_entries,
)
from .helpers import (
    _rmtree_robust,
    advisory_lock,
    atomic_write,
    ensure_dir,
    package_version,
    parse_version_tuple,
)
from .manifest import (
    ManifestData,
    add_providers,
    providers_sharing_dir,
    providers_sharing_file,
    read_manifest,
    read_manifest_data,
    remove_provider,
    write_manifest_data,
)

logger = logging.getLogger(__name__)


def _stamp_manifest_version_no_downgrade(mdata: ManifestData) -> None:
    """Set ``mdata.vaultspec_version`` to the running package version.

    Never downgrade: a registered migration whose ``target_version``
    exceeds the running package's version may have just bumped the
    manifest above the running release, and rewriting it back would
    silently re-flag the migration as pending on the next run.
    """
    running = package_version()
    if parse_version_tuple(running) > parse_version_tuple(mdata.vaultspec_version):
        mdata.vaultspec_version = running


def _fresh_install_schema_version() -> str:
    """Return the manifest version a freshly-installed workspace conforms to.

    A fresh install writes the current on-disk schema, so it must not
    leave any registered migration pending. When a migration targets a
    version above the running package - the normal state while a schema
    change and its migration ship together, before the release that
    carries them - the fresh manifest is stamped at that target so the
    migration is correctly seen as already satisfied.
    """
    from ..migrations import REGISTRY

    candidates = [package_version(), *(m.target_version for m in REGISTRY)]
    return max(candidates, key=parse_version_tuple)


def _persist_resolved_mode(path: Path, mdata: ManifestData, mode: InstallMode) -> None:
    """Persist *mode* to the committed declaration and echo it into *mdata*.

    Writes the shared source of truth (``.vaultspec/workspace.json`` via
    :func:`~vaultspec_core.core.workspace_mode.write_workspace_declaration`) and
    mirrors the resolved value into the gitignored per-machine manifest for
    local bookkeeping. An existing floor constraint
    (``minimum_vaultspec_version``) is preserved rather than dropped, since the
    provisioning mode and the floor are independent axes of the same
    declaration.

    The declaration writer takes its own advisory lock, so this function must
    not be called from within the manifest lock; *mdata* is mutated in place and
    persisted by the caller's own :func:`write_manifest_data` cycle.

    Invariant: callers run this only after
    :func:`~vaultspec_core.core.workspace_mode.resolve_install_mode`, which reads
    and validates any persisted declaration fail-fast. The re-read here is
    therefore expected to succeed - a corrupt declaration would already have
    aborted the run before any mutation - so this does not reintroduce a
    late-failure window.

    Args:
        path: Workspace root directory.
        mdata: Manifest data to stamp with the resolved mode echo; mutated in
            place, not written here.
        mode: The resolved provisioning mode to persist.
    """
    floor = _write_mode_declaration(path, mode)
    mdata.resolved_mode = mode
    mdata.resolved_floor_version = floor


def _write_mode_declaration(path: Path, mode: InstallMode) -> str | None:
    """Write the committed mode declaration, preserving any existing floor.

    The provisioning mode and the ``minimum_vaultspec_version`` floor are
    independent axes of the same committed declaration, so rewriting the mode
    must never drop a floor a prior run recorded. The write is deterministic
    (sorted keys, fixed indent) so re-writing the same mode leaves byte-identical
    content, which is what makes a repeated ``install --upgrade`` idempotent.

    Args:
        path: Workspace root directory.
        mode: The resolved provisioning mode to persist.

    Returns:
        The preserved floor constraint (or ``None``), so a caller echoing the
        declaration into the manifest need not re-read it.
    """
    from .workspace_mode import (
        WorkspaceDeclaration,
        read_workspace_declaration,
        write_workspace_declaration,
    )

    existing = read_workspace_declaration(path)
    floor = existing.minimum_vaultspec_version if existing is not None else None
    write_workspace_declaration(
        path,
        WorkspaceDeclaration(install_mode=mode, minimum_vaultspec_version=floor),
    )
    return floor


def _infer_upgrade_mode(target: Path, explicit: InstallMode | None) -> InstallMode:
    """Infer the provisioning mode for an ``install --upgrade`` (ADR Q6).

    Precedence mirrors provision-time resolution at its top: an explicit
    ``--mode`` flag wins (and is validated for impossible combinations), and an
    already-persisted declaration wins next, so a second upgrade is idempotent
    and a deliberate re-mode is honored. A legacy workspace with neither has its
    mode inferred from its own deployed state: dependency mode only when the
    canonical hook entries are ``uv run``-shaped *and* the target's
    ``pyproject.toml`` lists ``vaultspec-core``; tool mode in every other case.

    The hook-shape signal is read through the same ``_observed_precommit_mode``
    collector the doctor's mode-mismatch check consumes, so migration and
    diagnosis can never disagree on what a deployed artifact shape means - the
    ``install-mode`` constraint against introducing a second comparator.

    Args:
        target: Workspace root directory.
        explicit: The mode requested via ``--mode``, or ``None``.

    Returns:
        The inferred :class:`~vaultspec_core.core.enums.InstallMode` to persist
        and render against for this upgrade.

    Raises:
        VaultSpecError: Propagated from
            :func:`~vaultspec_core.core.workspace_mode.resolve_install_mode` when
            *explicit* names an impossible combination or a persisted declaration
            is malformed.
    """
    from .diagnosis.collectors import _observed_precommit_mode
    from .workspace_mode import read_workspace_declaration, resolve_install_mode

    if explicit is not None:
        return resolve_install_mode(target, explicit=explicit)
    if read_workspace_declaration(target) is not None:
        return resolve_install_mode(target, explicit=None)

    detected = resolve_install_mode(target, explicit=None)
    observed = _observed_precommit_mode(target)
    if detected is InstallMode.DEPENDENCY and observed is InstallMode.DEPENDENCY:
        return InstallMode.DEPENDENCY
    return InstallMode.TOOL


# Map provider argument names to Tool enum members. The per-tool entries derive
# from the Tool enum so adding a provider is a single-site change; "all" selects
# every tool and "core" selects none (framework-only). VALID_PROVIDERS and
# SYNC_PROVIDERS are derived from this map so the provider vocabulary has one
# source of truth.
_PROVIDER_TO_TOOLS: dict[str, list[Tool]] = {t.value: [t] for t in Tool}
_PROVIDER_TO_TOOLS["all"] = list(Tool)
_PROVIDER_TO_TOOLS["core"] = []

# Valid provider arguments for install/uninstall commands (every selector).
VALID_PROVIDERS = set(_PROVIDER_TO_TOOLS)


def _rel(target: Path, p: Path) -> str:
    return str(p.relative_to(target)).replace("\\", "/")


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


# The canonical CLI-invocation prefix each pre-commit hook entry is built from,
# keyed by provisioning mode. Dependency mode resolves ``vaultspec-core`` through
# the target project's own venv via ``uv run`` (byte-identical to the single
# prefix that existed before mode-awareness); tool mode resolves it through an
# ephemeral ``uvx`` invocation so it never enters the project's dependency set.
_MODE_ENTRY_PREFIX: dict[InstallMode, str] = {
    InstallMode.DEPENDENCY: "uv run --no-sync vaultspec-core",
    InstallMode.TOOL: "uvx --from vaultspec-core vaultspec-core",
}


def entry_prefix_for_mode(mode: InstallMode) -> str:
    """Return the canonical hook-entry command prefix for *mode*."""
    return _MODE_ENTRY_PREFIX[mode]


#: Backward-compatible module-level prefix, pinned to dependency mode. Modules
#: and diagnostics that still assume a single prefix (the doctor's
#: canonical-entry check) read this until they are made mode-aware; the
#: mode-parameterized renderers derive their prefix from
#: :func:`entry_prefix_for_mode` instead.
CANONICAL_ENTRY_PREFIX = entry_prefix_for_mode(InstallMode.DEPENDENCY)


def _is_git_repo(target: Path) -> bool:
    """Return ``True`` if *target* is inside a git repository.

    Detects both plain clones (``.git`` is a directory) and linked
    worktrees (``.git`` is a file pointing at the real gitdir).
    """
    return (target / ".git").exists()


# Paths under these prefixes are owned by vaultspec-core and may be
# untracked on install if they were historically committed.  Root-level
# files (CLAUDE.md, .mcp.json, .pre-commit-config.yaml, etc.) are excluded
# because operators may have legitimate reasons to commit them.
#
# Provider-scope directories (``.claude/``, ``.gemini/``, ``.agents/``,
# ``.codex/``) are included per ADR D1: "Each provider's scope directory
# recorded in the manifest, only for files that match the managed
# gitignore entries."  Concretely, ``get_recommended_entries`` emits
# these directories when the manifest records the provider as installed
# and the directory exists on disk; :func:`_untrack_managed_paths` only
# acts on entries it receives, so a provider that was never installed
# cannot be accidentally untracked.
_UNTRACK_PREFIXES: tuple[str, ...] = (
    ".vaultspec/",
    ".claude/",
    ".gemini/",
    ".agents/",
    ".codex/",
)

# Advisory-lock sentinel basenames we create ourselves.  Matched against
# the stripped candidate (no leading slash, no trailing slash) in the
# ``.lock`` ownership gate so that unrelated lockfiles (``uv.lock``,
# ``Cargo.lock``, ``bun.lock``, ``package-lock.json`` siblings, etc.)
# can never be untracked even if they reach the helper by accident.
_MANAGED_LOCK_SENTINELS: frozenset[str] = frozenset(
    {
        ".gitignore.lock",
        ".mcp.json.lock",
        ".pre-commit-config.yaml.lock",
    }
)


def _untrack_managed_paths(target: Path, entries: list[str]) -> list[str]:
    """Stop tracking managed paths that were committed before they became ignored.

    Iterates *entries* and retains only those under :data:`_UNTRACK_PREFIXES`
    or those that are advisory-lock sentinels (``*.lock`` that vaultspec
    itself produces).  For each retained candidate, invokes
    ``git rm --cached --ignore-unmatch -- <path>``.  No-ops when the target
    is not a git repository.  Subprocess failures are logged and do not
    raise.

    Args:
        target: Workspace root directory.
        entries: Managed gitignore entries computed for *target*.

    Returns:
        List of paths that were actually untracked (best-effort; may be
        empty if git is unavailable or nothing was previously tracked).
    """
    if not _is_git_repo(target):
        return []

    candidates: list[str] = []
    for entry in entries:
        # Skip glob patterns; git rm --cached does not expand them on our behalf.
        if "*" in entry or "?" in entry:
            continue
        # Strip leading slash from anchored entries ("/foo.lock" -> "foo.lock").
        candidate = entry[1:] if entry.startswith("/") else entry
        if not candidate:
            continue
        # Only act on paths we own.  Two ownership gates:
        #   1. under a prefix in :data:`_UNTRACK_PREFIXES` (currently only
        #      ``.vaultspec/``);
        #   2. a managed lock sentinel whose basename is in
        #      :data:`_MANAGED_LOCK_SENTINELS` **and** sits at the workspace
        #      root (``stem == basename``) so that subdirectory matches like
        #      ``docs/.gitignore.lock`` cannot hit the allowlist.
        #
        # The sentinel allowlist is explicit so that sibling lockfiles such
        # as ``uv.lock`` or ``Cargo.lock`` can never be untracked even if
        # a future caller passes them in.
        stem = candidate.rstrip("/")
        basename = stem.rsplit("/", 1)[-1]
        owned = (
            any(stem == prefix.rstrip("/") for prefix in _UNTRACK_PREFIXES)
            or any(stem.startswith(prefix) for prefix in _UNTRACK_PREFIXES)
            or (stem == basename and basename in _MANAGED_LOCK_SENTINELS)
        )
        if not owned:
            continue
        candidates.append(candidate)

    if not candidates:
        return []

    # The candidate list comes from :func:`get_recommended_entries` and is
    # bounded by the number of managed prefixes we own (``.vaultspec/``,
    # ``.claude/``, ``.gemini/``, ``.agents/``, ``.codex/``, plus a handful
    # of root-level lock sentinels).  It is safe to splat onto the argv.
    try:
        ls_result = subprocess.run(
            ["git", "-C", str(target), "ls-files", "--", *candidates],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        logger.warning("git ls-files probe failed during install untrack: %s", exc)
        return []

    tracked = [line.strip() for line in ls_result.stdout.splitlines() if line.strip()]
    if not tracked:
        return []

    # Chunk ``git rm --cached`` calls so the argv stays well below
    # ``ARG_MAX`` (~32 KiB on Windows, much larger on Linux) even on
    # legacy repos with thousands of tracked managed files.  Chunking
    # is preferred over ``--pathspec-from-file=-`` because that flag
    # was introduced in git 2.26 (March 2020) and some CI runners
    # still carry older git (notably Ubuntu 18.04 LTS with git 2.17).
    # 200 paths at ~256 chars each ~= 50 KiB which could spill ARG_MAX on
    # Windows under edge conditions; 100 keeps us firmly inside the
    # budget.
    _chunk_size = 100
    actually_untracked: list[str] = []
    for chunk_start in range(0, len(tracked), _chunk_size):
        chunk = tracked[chunk_start : chunk_start + _chunk_size]
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(target),
                    "rm",
                    "--cached",
                    "--ignore-unmatch",
                    "--",
                    *chunk,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            OSError,
        ) as exc:
            logger.warning(
                "git rm --cached failed during install untrack (chunk %d-%d): %s",
                chunk_start,
                chunk_start + len(chunk),
                exc,
            )
            # Stop dispatching further chunks but preserve the partial
            # result so callers and operators see exactly which paths
            # were untracked before the failure.
            break
        actually_untracked.extend(chunk)

    for path in actually_untracked:
        logger.info("Untracked previously-committed managed path: %s", path)
    return actually_untracked


# Patterns that must never be committed.  Used by the
# check-provider-artifacts pre-commit hook.
PROVIDER_ARTIFACT_PATTERNS: tuple[str, ...] = (
    ".mcp.json",
    "providers.lock",
    "CLAUDE.md",
    "GEMINI.md",
    "AGENTS.md",
    ".claude/",
    ".gemini/",
    ".codex/",
    ".agents/",
    ".vaultspec/_snapshots/",
)


def check_staged_provider_artifacts(cwd: Path | None = None) -> list[str]:
    """Return staged file paths that match provider artifact patterns.

    Runs ``git diff --cached --name-only --diff-filter=ACMR`` and filters
    against :data:`PROVIDER_ARTIFACT_PATTERNS`.  The ``ACMR`` filter excludes
    staged deletions so remediation commits (``git rm --cached ...``) are
    not blocked by the hook that recommends them.

    Args:
        cwd: Directory to run ``git`` in.  Defaults to the caller's current
            working directory (pre-commit hook behaviour).  Tests pass an
            explicit path to avoid mutating global process state.
    """
    cmd = ["git"]
    if cwd is not None:
        cmd.extend(["-C", str(cwd)])
    cmd.extend(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    staged = result.stdout.strip().splitlines()
    violations: list[str] = []
    for path in staged:
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        for pattern in PROVIDER_ARTIFACT_PATTERNS:
            if pattern.endswith("/"):
                # Directory pattern: match any path segment exactly
                dirname = pattern.rstrip("/")
                if any(seg == dirname for seg in parts):
                    violations.append(path)
                    break
            elif normalized == pattern or parts[-1] == pattern:
                violations.append(path)
                break
    return violations


# Mode-independent pre-commit hook metadata: the CLI subcommand each hook
# invokes plus its non-entry pre-commit fields. The ``entry`` is derived per
# mode by prefixing the subcommand with the mode's canonical entry prefix. The
# insertion order here is the order hooks are scaffolded into
# ``.pre-commit-config.yaml`` and must be preserved.
_HOOK_SUBCOMMAND: dict[PrecommitHook, str] = {
    PrecommitHook.VAULT_FIX: "vault check all --fix",
    PrecommitHook.VAULT_SANITIZE_ANNOTATIONS: "vault sanitize annotations",
    PrecommitHook.CHECK_PROVIDER_ARTIFACTS: "check-providers",
    PrecommitHook.SPEC_CHECK: "spec doctor",
}
_HOOK_META: dict[PrecommitHook, dict[str, object]] = {
    PrecommitHook.VAULT_FIX: {"name": "Vault fix", "types": ["markdown"]},
    PrecommitHook.VAULT_SANITIZE_ANNOTATIONS: {
        "name": "Vault sanitize annotations",
        "types": ["markdown"],
    },
    PrecommitHook.CHECK_PROVIDER_ARTIFACTS: {
        "name": "Check provider artifacts",
        "always_run": True,
    },
    PrecommitHook.SPEC_CHECK: {"name": "Spec check", "types": ["markdown"]},
}


def hook_defs_for_mode(mode: InstallMode) -> dict[PrecommitHook, dict[str, object]]:
    """Return the hook-field map for *mode*, keyed by :class:`PrecommitHook`.

    Each value merges the mode-independent metadata (name, filter fields) with
    an ``entry`` built from the mode's canonical prefix and the hook's
    subcommand, so dependency mode renders ``uv run --no-sync vaultspec-core
    ...`` and tool mode renders ``uvx --from vaultspec-core vaultspec-core
    ...``.
    """
    prefix = entry_prefix_for_mode(mode)
    defs: dict[PrecommitHook, dict[str, object]] = {}
    for hook, meta in _HOOK_META.items():
        # Preserve the original field order (name, entry, then the hook's
        # filter field) so the scaffolded YAML is byte-stable across modes.
        value: dict[str, object] = {"name": meta["name"]}
        value["entry"] = f"{prefix} {_HOOK_SUBCOMMAND[hook]}"
        for key, field in meta.items():
            if key != "name":
                value[key] = field
        defs[hook] = value
    return defs


def canonical_precommit_hooks_for_mode(mode: InstallMode) -> list[dict[str, object]]:
    """Return the full canonical pre-commit hook list rendered for *mode*."""
    return [
        {
            "id": hook.value,
            **meta,
            "language": "system",
            "pass_filenames": False,
        }
        for hook, meta in hook_defs_for_mode(mode).items()
    ]


def canonical_hook_entries_for_mode(mode: InstallMode) -> dict[str, str]:
    """Return each canonical hook ID mapped to its expected entry for *mode*."""
    return {
        hook.value: str(meta["entry"])
        for hook, meta in hook_defs_for_mode(mode).items()
    }


CANONICAL_HOOK_IDS: frozenset[str] = frozenset(h.value for h in PrecommitHook)

#: Backward-compatible module-level canonical hooks and entries, pinned to
#: dependency mode. The doctor's canonical-entry check still imports
#: ``CANONICAL_HOOK_ENTRIES`` and compares against the single dependency-mode
#: shape; making that check mode-aware is the next phase. ``_scaffold_precommit``
#: renders through :func:`canonical_precommit_hooks_for_mode` instead.
CANONICAL_PRECOMMIT_HOOKS: list[dict[str, object]] = canonical_precommit_hooks_for_mode(
    InstallMode.DEPENDENCY
)
CANONICAL_HOOK_ENTRIES: dict[str, str] = canonical_hook_entries_for_mode(
    InstallMode.DEPENDENCY
)

# All managed hook IDs for uninstall filtering.
_ALL_MANAGED_HOOK_IDS: frozenset[str] = CANONICAL_HOOK_IDS


def _scaffold_precommit(
    target: Path, *, dry_run: bool = False, mode: InstallMode | None = None
) -> list[tuple[str, str]]:
    """Scaffold or merge vaultspec-core hooks into .pre-commit-config.yaml.

    Ensures the full canonical hook set is present with canonical entry
    patterns.  Existing hooks with matching IDs are updated to the
    canonical entry; missing hooks are appended.

    The entry each hook is rendered with follows the resolved provisioning
    mode: dependency mode keeps the ``uv run --no-sync vaultspec-core`` prefix,
    tool mode uses ``uvx --from vaultspec-core vaultspec-core``. When *mode* is
    ``None`` it is resolved from the committed workspace declaration via
    :func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`, whose
    legacy-absent rule renders dependency mode so a workspace provisioned
    before ``install-mode`` keeps its existing hook entries. The fresh-install
    caller passes its resolved mode explicitly, because the declaration is
    written only after scaffolding.

    Skips scaffolding entirely when ``prek.toml`` is present at *target*:
    prek treats ``.pre-commit-config.yaml`` as a duplicate configuration
    source and emits a warning, and writing both would cause neither tool
    to execute our hooks.  The operator is expected to transplant hooks
    into ``prek.toml`` manually.
    """
    if mode is None:
        from .workspace_mode import resolve_render_mode

        mode = resolve_render_mode(target)
    canonical_hooks = canonical_precommit_hooks_for_mode(mode)

    if (target / "prek.toml").exists():
        logger.info(
            "prek.toml detected at %s; skipping .pre-commit-config.yaml scaffold. "
            "Add vaultspec-core hooks to prek.toml manually.",
            target,
        )
        if (target / ".pre-commit-config.yaml").exists():
            logger.warning(
                "Both prek.toml and .pre-commit-config.yaml are present at %s. "
                "prek reads prek.toml exclusively; vaultspec will not refresh the "
                "YAML hooks.  Remove .pre-commit-config.yaml or migrate its hooks "
                "into prek.toml to avoid stale pre-commit config.",
                target,
            )
        return []

    config_file = target / ".pre-commit-config.yaml"

    with advisory_lock(config_file):
        if config_file.exists():
            try:
                raw = config_file.read_text(encoding="utf-8")
                data = yaml.safe_load(raw) or {}
                if not isinstance(data, dict):
                    return []
            except (yaml.YAMLError, OSError):
                return []

            repos = data.setdefault("repos", [])
            if not isinstance(repos, list):
                return []

            # Find or create local repo
            local_repos = [
                r for r in repos if isinstance(r, dict) and r.get("repo") == "local"
            ]
            if local_repos:
                local_repo = local_repos[0]
                existing_hooks = local_repo.setdefault("hooks", [])
                if not isinstance(existing_hooks, list):
                    return []

                existing_by_id = {
                    h.get("id"): h for h in existing_hooks if isinstance(h, dict)
                }

                changed = False

                for canonical in canonical_hooks:
                    hook_id = str(canonical["id"])
                    if hook_id in existing_by_id:
                        existing = existing_by_id[hook_id]
                        if existing.get("entry") != canonical["entry"]:
                            existing["entry"] = canonical["entry"]
                            logger.info(
                                "Updated pre-commit hook '%s' entry"
                                " to canonical pattern",
                                hook_id,
                            )
                            changed = True
                    else:
                        existing_hooks.append(dict(canonical))
                        logger.info("Added pre-commit hook '%s'", str(canonical["id"]))
                        changed = True

                if not changed:
                    return []
            else:
                repos.append(
                    {
                        "repo": "local",
                        "hooks": [dict(h) for h in canonical_hooks],
                    }
                )

            if not dry_run:
                atomic_write(
                    config_file,
                    yaml.dump(
                        data,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    ),
                )
            return [(".pre-commit-config.yaml", "precommit")]

        if not dry_run:
            data = {
                "repos": [
                    {
                        "repo": "local",
                        "hooks": [dict(h) for h in canonical_hooks],
                    }
                ]
            }
            atomic_write(
                config_file,
                yaml.dump(
                    data,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                ),
            )
        return [(".pre-commit-config.yaml", "precommit")]


def _validate_provider(provider: str) -> None:
    """Validate that *provider* is a known provider name.

    Raises:
        ProviderError: If *provider* is not in :data:`VALID_PROVIDERS`.
    """
    if provider not in VALID_PROVIDERS:
        raise ProviderError(
            f"Unknown provider '{provider}'. "
            f"Valid: {', '.join(sorted(VALID_PROVIDERS))}"
        )


def _validate_skip(skip: set[str] | None, *, allow_core: bool = True) -> set[str]:
    """Validate and normalise a *skip* set.

    Raises:
        ProviderError: If any value in *skip* is not a valid component name.
    """
    if not skip:
        return set()
    # "all" is not a valid skip target  - you'd just not run the command.
    # "mcp" is a valid skip target but is not a provider.
    allowed = (VALID_PROVIDERS - {"all"}) | {"mcp", "precommit"}
    if not allow_core:
        allowed.discard("core")
    bad = skip - allowed
    if bad:
        raise ProviderError(
            f"Invalid --skip value(s): {', '.join(sorted(bad))}. "
            f"Valid: {', '.join(sorted(allowed))}"
        )
    return skip


def _filter_tools(tools: list[Tool], skip: set[str]) -> list[Tool]:
    """Remove tools whose provider name is in *skip*."""
    if not skip:
        return tools
    return [t for t in tools if t.value not in skip]


def init_run(
    force: bool = False,
    provider: str = "all",
    skip: set[str] | None = None,
    mode: InstallMode | None = None,
) -> list[tuple[str, str]]:
    """Scaffold the .vaultspec/ and .vault/ directory structure.

    Args:
        force: Override contents if already exists.
        provider: Provider to install.
        skip: Set of component names to skip (``core`` and/or provider names).
        mode: Resolved provisioning mode used to render the MCP definition and
            pre-commit hook entries. The fresh-install caller passes this
            explicitly because the committed workspace declaration is written
            only after scaffolding; ``None`` lets the renderers fall back to
            the declaration (dependency mode for a legacy workspace).

    Returns:
        A deduplicated list of ``(relative_path, label)`` tuples for all
        created directories and files.
    """
    from vaultspec_core.config import get_config, reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    from .exceptions import ResourceExistsError

    skip = skip or set()
    skip_core = "core" in skip

    cfg = get_config()
    target = _t.get_context().target_dir
    fw_dir = target / cfg.framework_dir

    created: list[tuple[str, str]] = []

    if not skip_core:
        if fw_dir.exists() and not force:
            raise ResourceExistsError(
                f"{fw_dir} already exists. Use --force to overwrite."
            )

        created = _scaffold_core(target)

        # Seed builtin content directly into .vaultspec/
        from vaultspec_core.builtins import seed_builtins

        seeded = seed_builtins(fw_dir, force=force)
        for rel, _action in seeded:
            created.append((f".vaultspec/{rel}", "builtin"))

        # Snapshot builtins for revert support
        from .revert import snapshot_builtins

        snapshot_builtins(fw_dir)

    # Re-resolve workspace after scaffolding
    reset_config()
    layout = resolve_workspace(target_override=target)
    init_paths(layout)

    # Scaffold provider directories
    tools = _filter_tools(_PROVIDER_TO_TOOLS.get(provider, []), skip)
    for tool in tools:
        created.extend(_scaffold_provider(target, tool))

    if "mcp" not in skip:
        from .mcps import mcp_sync

        mcp_result = mcp_sync(mode=mode)
        if mcp_result.items:
            created.append((".mcp.json", "mcp"))
    if "precommit" not in skip:
        created.extend(_scaffold_precommit(target, mode=mode))

    # Write provider manifest
    provider_names = [t.value for t in tools]
    if provider_names:
        add_providers(target, provider_names)

    # Deduplicate by relative path, preserving order
    seen: dict[str, str] = {}
    for rel, label in created:
        seen.setdefault(rel, label)

    return list(seen.items())


def _ensure_tool_configs(path: Path) -> None:
    """Ensure TOOL_CONFIGS is populated, bootstrapping if needed.

    On a fresh project where ``.vaultspec/`` doesn't exist yet, uses a
    temporary directory as the workspace root so ``init_paths()`` can resolve
    the layout and populate TOOL_CONFIGS without touching the real filesystem.
    """
    import tempfile

    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    try:
        if _t.get_context().tool_configs:
            return
    except LookupError:
        pass

    fw_dir = path / ".vaultspec"
    if fw_dir.exists():
        reset_config()
        layout = resolve_workspace(target_override=path)
        init_paths(layout)
        return

    # Bootstrap in a temporary directory to avoid TOCTOU on the real path.
    # Resolve workspace against the temp dir, then re-initialize with the
    # real target so tool_config paths reference the actual workspace.
    tmp = Path(tempfile.mkdtemp())
    try:
        tmp_fw = tmp / ".vaultspec"
        tmp_fw.mkdir(parents=True, exist_ok=True)

        reset_config()
        layout = resolve_workspace(target_override=tmp)
        # Replace the temp target with the real path so tool_configs point correctly
        from vaultspec_core.config.workspace import WorkspaceLayout

        real_layout = WorkspaceLayout(
            target_dir=path,
            vault_dir=path / ".vault",
            vaultspec_dir=path / ".vaultspec",
            mode=layout.mode,
            git=layout.git,
        )
        init_paths(real_layout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_run(
    path: Path,
    provider: str = "all",
    upgrade: bool = False,
    dry_run: bool = False,
    force: bool = False,
    skip: set[str] | None = None,
    mode: InstallMode | None = None,
) -> dict[str, Any]:
    """Deploy the vaultspec framework to a project directory.

    Args:
        path: Target directory.
        provider: Provider to install (``all``, ``core``, ``claude``, etc.).
        upgrade: Re-sync builtin rules without re-scaffolding.
        dry_run: Preview the manifest of files that would be created.
        force: Override contents if installation already exists.
        skip: Set of component names to skip (``core`` and/or provider names).
        mode: Explicit provisioning mode from the ``--mode`` flag, or ``None``
            to let the workspace fall back to the default. The resolved mode is
            persisted once at provision time to the committed workspace
            declaration and echoed into the manifest.

    Returns:
        A dict describing the result:
        - ``"action"``: ``"dry_run"``, ``"upgrade"``, or ``"install"``
        - ``"items"``: list of ``(path, label)`` tuples (for dry_run);
          list of ``(builtin_path, action)`` tuples (for upgrade)

    Raises:
        ProviderError: If *provider* is invalid.
        ResourceExistsError: If already installed and *force*/*upgrade* not set.
    """
    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import WorkspaceError, resolve_workspace
    from vaultspec_core.core.types import init_paths

    from .exceptions import ResourceExistsError

    _validate_provider(provider)
    skip = _validate_skip(skip)

    # Bootstrap a minimal context so downstream code can read target_dir
    _t.set_context(
        _t.WorkspaceContext(
            root_dir=path,
            target_dir=path,
            rules_src_dir=path,
            skills_src_dir=path,
            agents_src_dir=path,
            system_src_dir=path,
            templates_dir=path,
            hooks_dir=path,
        )
    )

    skip_core = "core" in skip

    if skip_core and not (path / ".vaultspec").exists():
        raise VaultSpecError(
            f"Cannot skip core: .vaultspec/ does not exist at {path}.",
            hint="Install core first, then use --skip core on subsequent installs.",
        )

    # Resolve the provisioning mode once, at provision time, via the Q5
    # precedence chain (explicit flag, persisted declaration, pyproject
    # detection, default tool mode). An explicit request that names an
    # impossible combination - dependency mode with no pyproject.toml - raises a
    # loud, typed refusal here rather than silently falling back.
    from .workspace_mode import resolve_install_mode

    resolved_mode = resolve_install_mode(path, explicit=mode)

    if upgrade and dry_run:
        _ensure_tool_configs(path)
        items: list[tuple[str, str]] = []
        if not skip_core:
            from vaultspec_core.builtins import seed_builtins

            items = seed_builtins(path / ".vaultspec", force=True, dry_run=True)

        # The real upgrade re-seeds builtins AND runs the provider sync, which
        # backfills new provider files and structural directories. Preview that
        # provider-side work too so the dry-run enumerates what the real run
        # changes rather than only the builtin seed (issue #134). Only the
        # changed entries are surfaced to keep the preview signal-dense; an
        # unchanged provider tree contributes nothing.
        if path.joinpath(".vaultspec").exists():
            sync_target = provider if provider not in ("all", "core") else "all"
            try:
                sync_results = sync_provider(sync_target, dry_run=True, skip=skip)
            except (VaultSpecError, OSError) as exc:
                logger.debug("Upgrade dry-run provider preview skipped: %s", exc)
                sync_results = []
            seen_preview = {rel for rel, _ in items}
            for sync_result in sync_results:
                for rel, action in sync_result.items:
                    if action in ("[UNCHANGED]", "[SKIP]"):
                        continue
                    if rel in seen_preview:
                        continue
                    seen_preview.add(rel)
                    items.append((rel, action))

        return {
            "action": "upgrade",
            "items": items,
            "path": path,
            "dry_run": True,
        }

    if dry_run:
        _ensure_tool_configs(path)

        manifest: list[tuple[str, str]] = []

        if not skip_core:
            manifest = _scaffold_core(path, dry_run=True)

            # Include builtin files that would be seeded
            from vaultspec_core.builtins import list_builtins

            for builtin_rel in list_builtins():
                manifest.append((f".vaultspec/{builtin_rel}", "builtin"))

        tools = _filter_tools(_PROVIDER_TO_TOOLS.get(provider, []), skip)
        for tool in tools:
            manifest.extend(_scaffold_provider(path, tool, dry_run=True))
        if "mcp" not in skip:
            from .mcps import mcp_sync

            mcp_result = mcp_sync(dry_run=True, mode=resolved_mode)
            if mcp_result.items:
                manifest.append((".mcp.json", "mcp"))
        if "precommit" not in skip:
            manifest.extend(_scaffold_precommit(path, dry_run=True, mode=resolved_mode))

        # Deduplicate preserving order (by relative path)
        seen: dict[str, str] = {}
        for rel, label in manifest:
            seen.setdefault(rel, label)

        return {"action": "dry_run", "items": list(seen.items()), "path": path}

    if upgrade:
        try:
            layout = resolve_workspace(target_override=path)
            init_paths(layout)
        except WorkspaceError as e:
            raise WorkspaceNotInitializedError(
                f"Cannot upgrade: {e}",
                hint=f"Run 'vaultspec-core install {path}' first.",
            ) from e

        # Q6 migration: refine the provision-time resolution with this
        # workspace's deployed state. A legacy workspace carries no persisted
        # mode, so infer it from the observed hook shape and the pyproject
        # dependency listing; a workspace that already declares a mode keeps it,
        # which is what makes a repeated upgrade idempotent. This supersedes the
        # value resolve_install_mode computed at entry, since only here is the
        # deployed hook shape folded in.
        resolved_mode = _infer_upgrade_mode(path, mode)

        seeded: list[tuple[str, str]] = []
        if not skip_core:
            # Re-seed builtins (force=True overwrites existing)
            from vaultspec_core.builtins import seed_builtins

            fw_dir = path / ".vaultspec"
            seeded = seed_builtins(fw_dir, force=True)

            # Re-snapshot builtins for revert support
            from .revert import snapshot_builtins

            snapshot_builtins(fw_dir)

        # Run pending schema migrations BEFORE the sync. ``sync_provider``
        # ends with ``mdata.vaultspec_version = package_version()``, which
        # would otherwise mask any migration whose ``target_version``
        # equals the running release: ``run_pending_migrations`` would
        # read the just-bumped version and find nothing pending. Running
        # the driver first preserves the pre-upgrade manifest version so
        # the registry sees the real "needs migration" state, applies
        # the pending entries, and then ``sync_provider`` re-bumps to
        # the running version on its way out.
        from ..migrations import run_pending_migrations

        run_pending_migrations(path)

        # Persist the inferred declaration BEFORE the provider sync and the hook
        # scaffold re-render their artifacts. Both renderers resolve their mode
        # from the committed declaration (via resolve_render_mode); on a legacy
        # workspace with no declaration that fallback renders dependency mode, so
        # an inference that landed tool mode would otherwise leave uv-run-shaped
        # artifacts contradicting the tool-mode declaration written moments
        # later. Writing it here threads the inferred mode into this same run's
        # rendering, mirroring the fresh-install ordering. The manifest echo and
        # floor reconciliation still run once, later, via _persist_resolved_mode.
        _write_mode_declaration(path, resolved_mode)

        sync_target = provider if provider not in ("all", "core") else "all"
        # `sync_provider` rejects `core` in its skip set (`allow_core=False`).
        # `install_run` accepts `core` because it skips the framework scaffold;
        # filter it out before forwarding to the sync pass.
        # Forward `force`: `--upgrade` and `--force` are separate flags;
        # `install --upgrade` (without `--force`) must preserve user-authored
        # content. The pre-collapse hardcoded `force=True` was an asymmetry
        # against the fresh-install path and silently overwrote user content
        # on every upgrade. See PR #116 review thread r3260188496.
        sync_provider(sync_target, force=force, skip=skip - {"core"})

        if "precommit" not in skip:
            _scaffold_precommit(path, mode=resolved_mode)

        # Update manifest timestamps and version
        import datetime

        mdata = read_manifest_data(path)
        if not mdata.installed_at:
            mdata.installed_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
        _stamp_manifest_version_no_downgrade(mdata)

        # Re-opt-in gitignore management on --upgrade --force
        if force:
            ensure_gitignore_block(
                path,
                get_recommended_entries(path),
                state=ManagedState.PRESENT,
            )
            mdata.gitignore_managed = True

        from .diagnosis.collectors import collect_precommit_state
        from .diagnosis.signals import PrecommitSignal

        pc_signal = collect_precommit_state(path)
        mdata.precommit_managed = pc_signal not in (
            PrecommitSignal.NO_FILE,
            PrecommitSignal.NO_HOOKS,
        )

        _persist_resolved_mode(path, mdata, resolved_mode)
        write_manifest_data(path, mdata)

        # Reconcile git index with the managed gitignore block so that
        # historically-committed state files (e.g. .vaultspec/providers.json
        # from a pre-managed-block install) stop showing up as dirty on
        # every subsequent run.
        _untrack_managed_paths(path, get_recommended_entries(path))

        return {"action": "upgrade", "items": seeded, "path": path}

    fw_dir = path / ".vaultspec"
    if fw_dir.exists() and not force and not skip_core:
        raise ResourceExistsError(
            f"vaultspec is already installed at {path}. "
            "Use --upgrade to update, --force to override, or remove it "
            f"first with 'vaultspec-core uninstall {path}'."
        )

    created = init_run(force=force, provider=provider, skip=skip, mode=resolved_mode)

    reset_config()
    layout = resolve_workspace(target_override=path)
    init_paths(layout)

    # Persist the committed declaration before the provider sync below re-renders
    # the MCP config and pre-commit hooks. Those renderers resolve their mode
    # from the declaration; writing it here means the just-resolved mode governs
    # the sync pass instead of the legacy-absent dependency bridge, which would
    # otherwise clobber the tool-mode artifacts init_run just wrote. The manifest
    # echo and floor reconciliation still happen once, later, via
    # _persist_resolved_mode after the manifest is read.
    _write_mode_declaration(path, resolved_mode)

    post_errors: list[str] = []

    sync_target = provider if provider not in ("all", "core") else "all"
    try:
        # Filter `core` out: `sync_provider` rejects it, but `install_run`
        # accepts it as a "framework only, skip provider sync" hint.
        # Forward `force`: `install --force` must propagate to the sync
        # pass so user-authored system prompts and provider configs are
        # overwritten consistently with the rest of the install.
        sync_provider(sync_target, force=force, skip=skip - {"core"})
    except (VaultSpecError, OSError) as exc:
        logger.warning("Sync failed during install: %s", exc)
        post_errors.append(f"sync: {exc}")

    # Count actual source resources (what the user authored)
    from .agents import collect_agents
    from .mcps import collect_mcp_servers
    from .rules import collect_rules
    from .skills import collect_skills

    source_counts = {
        "rules": len(collect_rules()),
        "skills": len(collect_skills()),
        "agents": len(collect_agents()),
        "mcps": len(collect_mcp_servers()),
    }

    tools = _filter_tools(_PROVIDER_TO_TOOLS.get(provider, []), skip)
    provider_names = [t.value for t in tools]
    has_mcp = (path / ".mcp.json").exists()

    # Manage gitignore block
    recommended = get_recommended_entries(path)

    gi_written = ensure_gitignore_block(path, recommended, state=ManagedState.PRESENT)
    if gi_written:
        logger.info("Added vaultspec managed block to .gitignore")

    # Manage gitattributes block
    ga_written = ensure_gitattributes_block(path, state=ManagedState.PRESENT)
    if ga_written:
        logger.info("Added vaultspec managed block to .gitattributes")

    # Populate v2.0 manifest fields
    import datetime

    gi_path = path / ".gitignore"
    ga_path = path / ".gitattributes"
    mdata = read_manifest_data(path, strict=True)

    # Robust detection: if it's there, it's managed.
    block_present = False
    if gi_path.exists():
        try:
            content = gi_path.read_text(encoding="utf-8")
            begins, ends = _find_markers(content.splitlines())
            block_present = len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]

        except (OSError, UnicodeDecodeError):
            pass

    ga_block_present = False
    if ga_path.exists():
        try:
            content = ga_path.read_text(encoding="utf-8")
            ga_block_present = _ga_has_valid_block(content.splitlines())
        except (OSError, UnicodeDecodeError):
            pass

    mdata.gitignore_managed = block_present
    mdata.gitattributes_managed = ga_block_present

    from .diagnosis.collectors import collect_precommit_state
    from .diagnosis.signals import PrecommitSignal

    pc_signal = collect_precommit_state(path)
    mdata.precommit_managed = pc_signal not in (
        PrecommitSignal.NO_FILE,
        PrecommitSignal.NO_HOOKS,
    )

    mdata.vaultspec_version = _fresh_install_schema_version()
    mdata.installed_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
    for name in provider_names:
        mdata.provider_state.setdefault(name, {})
        mdata.provider_state[name]["installed_at"] = mdata.installed_at
    _persist_resolved_mode(path, mdata, resolved_mode)
    write_manifest_data(path, mdata)

    # Reconcile git index with the managed gitignore block so that
    # historically-committed state files (e.g. .vaultspec/providers.json
    # from a pre-managed-block install) stop showing up as dirty on
    # every subsequent run.
    _untrack_managed_paths(path, recommended)

    result: dict[str, Any] = {
        "action": "install",
        "items": created,
        "source_counts": source_counts,
        "providers": provider_names,
        "has_mcp": has_mcp,
        "path": path,
    }
    if post_errors:
        result["errors"] = post_errors
    return result


def uninstall_run(
    path: Path,
    provider: str = "all",
    keep_vault: bool = False,
    dry_run: bool = False,
    force: bool = False,
    skip: set[str] | None = None,
) -> dict[str, Any]:
    """Remove the vaultspec framework from a project directory.

    Args:
        path: Target directory.
        provider: Provider to uninstall (``all``, ``core``, ``<provider>``).
        keep_vault: Preserve ``.vault/`` documentation directory.
        dry_run: Preview what would be removed without deleting.
        force: Required to execute. Uninstall is destructive.
        skip: Set of component names to skip (``core`` and/or provider names).

    Returns:
        A dict describing the result:
        - ``"action"``: ``"dry_run"`` or ``"uninstall"``
        - ``"removed"``: list of ``(path, label)`` tuples

    Raises:
        ProviderError: If *provider* is invalid or *force* not set.
    """
    _validate_provider(provider)
    skip = _validate_skip(skip)

    # Safety gate: require --force for destructive operations
    if not force and not dry_run:
        raise ProviderError(
            "Uninstall is destructive. Pass --force to confirm, "
            "or use --dry-run to preview."
        )

    # Bootstrap a minimal context so _ensure_tool_configs can proceed
    _t.set_context(
        _t.WorkspaceContext(
            root_dir=path,
            target_dir=path,
            rules_src_dir=path,
            skills_src_dir=path,
            agents_src_dir=path,
            system_src_dir=path,
            templates_dir=path,
            hooks_dir=path,
        )
    )
    _ensure_tool_configs(path)

    # Uninstalling "core" cascades to all providers
    effective_provider = "all" if provider == "core" else provider

    removed: list[tuple[str, str]] = []  # (path, label)

    # Map directory names → component owners (for skip filtering).
    # .agents/ is shared by antigravity, gemini, and codex (all place
    # skills there via init_paths), so it must be preserved when any of
    # its owners is skipped.
    _dir_owners: dict[str, list[str]] = {
        ".vaultspec": ["core"],
        ".vault": ["vault"],
        ".claude": ["claude"],
        ".gemini": ["gemini"],
        ".agents": ["antigravity", "gemini", "codex"],
        ".codex": ["codex"],
    }
    dir_labels: dict[str, str] = {
        ".vaultspec": "core",
        ".vault": "vault",
        ".claude": "claude",
        ".gemini": "gemini",
        ".agents": "antigravity",
        ".codex": "codex",
    }
    file_labels: dict[str, str] = {
        "CLAUDE.md": "claude (config)",
        "GEMINI.md": "gemini (config)",
        "AGENTS.md": "codex (config)",
        ".mcp.json": "mcp",
    }
    # Map file names → owning component for skip checks
    _file_owner: dict[str, str] = {
        "CLAUDE.md": "claude",
        "GEMINI.md": "gemini",
        "AGENTS.md": "codex",
    }

    errors: list[str] = []

    # Capture manifest state before potential destruction
    try:
        mdata_before = read_manifest_data(path)
    except Exception:
        # Fallback if manifest is already gone or corrupted
        mdata_before = ManifestData()

    if effective_provider == "all":
        from .helpers import atomic_write

        # Remove everything (respecting skip).
        # .vaultspec is deleted LAST so the manifest survives partial failures.
        managed_dirs = [
            path / ".claude",
            path / ".gemini",
            path / ".agents",
            path / ".codex",
        ]
        if not keep_vault:
            managed_dirs.append(path / ".vault")
        managed_dirs.append(path / ".vaultspec")

        managed_files = [
            path / "CLAUDE.md",
            path / "GEMINI.md",
            path / "AGENTS.md",
        ]

        # Surgical .mcp.json cleanup BEFORE directory removal so the
        # registry in .vaultspec/mcps/ is still readable.
        mcp_path = path / ".mcp.json"
        if "mcp" not in skip:
            from .mcps import mcp_uninstall

            uninstalled = mcp_uninstall(path, dry_run=dry_run)
            if uninstalled:
                removed.append((_rel(path, mcp_path), "mcp"))

        for d in managed_dirs:
            owners = _dir_owners.get(d.name, [])
            if owners and any(o in skip for o in owners):
                skipped = [o for o in owners if o in skip]
                logger.info("Skipping %s (--skip %s)", d.name, ", ".join(skipped))
                continue
            owner = dir_labels.get(d.name, "")
            if d.exists():
                if not dry_run:
                    try:
                        _rmtree_robust(d)
                    except OSError as exc:
                        errors.append(f"Failed to remove {_rel(path, d)}: {exc}")
                        continue
                removed.append((str(d).replace("\\", "/") + "/", owner))

        for f in managed_files:
            owner = _file_owner.get(f.name, "")
            if owner in skip:
                logger.info("Skipping %s (--skip %s)", f.name, owner)
                continue
            if f.exists():
                if not dry_run:
                    try:
                        f.unlink()
                    except OSError as exc:
                        errors.append(f"Failed to remove {_rel(path, f)}: {exc}")
                        continue
                label = file_labels.get(f.name, "")
                removed.append((str(f).replace("\\", "/"), label))

        # Surgical .pre-commit-config.yaml cleanup: remove vaultspec-core hooks
        precommit_path = path / ".pre-commit-config.yaml"
        if "precommit" not in skip:
            if precommit_path.exists() and not dry_run:
                try:
                    raw = precommit_path.read_text(encoding="utf-8")
                    data = yaml.safe_load(raw)
                    if isinstance(data, dict):
                        repos = data.get("repos", [])
                        if isinstance(repos, list):
                            changed = False
                            new_repos = []
                            for r in repos:
                                if isinstance(r, dict) and r.get("repo") == "local":
                                    hooks = r.get("hooks", [])
                                    if isinstance(hooks, list):
                                        new_hooks = [
                                            h
                                            for h in hooks
                                            if isinstance(h, dict)
                                            and h.get("id") not in _ALL_MANAGED_HOOK_IDS
                                        ]
                                        if len(new_hooks) != len(hooks):
                                            r["hooks"] = new_hooks
                                            changed = True
                                        if new_hooks:
                                            new_repos.append(r)
                                    else:
                                        new_repos.append(r)
                                else:
                                    new_repos.append(r)

                            if changed:
                                if new_repos:
                                    data["repos"] = new_repos
                                    atomic_write(
                                        precommit_path,
                                        yaml.dump(
                                            data,
                                            sort_keys=False,
                                            default_flow_style=False,
                                            allow_unicode=True,
                                        ),
                                    )
                                else:
                                    del data["repos"]
                                    if not data:
                                        precommit_path.unlink()
                                    else:
                                        atomic_write(
                                            precommit_path,
                                            yaml.dump(
                                                data,
                                                sort_keys=False,
                                                default_flow_style=False,
                                                allow_unicode=True,
                                            ),
                                        )
                                removed.append(
                                    (_rel(path, precommit_path), "precommit")
                                )
                                mdata_u = read_manifest_data(path)
                                if mdata_u.precommit_managed:
                                    mdata_u.precommit_managed = False
                                    write_manifest_data(path, mdata_u)
                except (yaml.YAMLError, OSError):
                    pass
            elif precommit_path.exists() and dry_run:
                try:
                    raw = precommit_path.read_text(encoding="utf-8")
                    if any(f"id: {hid}" in raw for hid in _ALL_MANAGED_HOOK_IDS):
                        removed.append((_rel(path, precommit_path), "precommit"))
                except OSError:
                    pass

    else:
        # Per-provider uninstall with shared directory protection
        tools = _filter_tools(_PROVIDER_TO_TOOLS.get(effective_provider, []), skip)
        for tool in tools:
            dirs, files = _collect_provider_artifacts(path, tool)

            for d in dirs:
                if not d.exists():
                    continue
                sharing = providers_sharing_dir(path, d, exclude=effective_provider)
                if sharing:
                    logger.info(
                        "Preserving %s (still used by: %s)",
                        d.relative_to(path),
                        ", ".join(sorted(sharing)),
                    )
                    continue

                if not dry_run:
                    try:
                        _rmtree_robust(d)
                    except OSError as exc:
                        errors.append(f"Failed to remove {_rel(path, d)}: {exc}")
                        continue
                removed.append((str(d).replace("\\", "/") + "/", tool.value))

            for f in files:
                if not f.exists():
                    continue
                sharing = providers_sharing_file(path, f, exclude=effective_provider)
                if sharing:
                    logger.info(
                        "Preserving %s (still used by: %s)",
                        f.relative_to(path),
                        ", ".join(sorted(sharing)),
                    )
                    continue
                if not dry_run:
                    try:
                        f.unlink()
                    except OSError as exc:
                        errors.append(f"Failed to remove {_rel(path, f)}: {exc}")
                        continue
                removed.append((str(f).replace("\\", "/"), f"{tool.value} (config)"))

        # Update manifest once after all tools are removed from disk
        if not dry_run:
            for tool in tools:
                remove_provider(path, tool.value)

    # Re-sync gitignore and gitattributes blocks
    if not dry_run:
        try:
            mdata_after = read_manifest_data(path)
        except Exception:
            mdata_after = ManifestData()

        recommended = get_recommended_entries(path)
        # If no providers remain and we are not keeping the vault, remove the block.
        # Otherwise, we sync it if it was managed before.
        if not mdata_after.installed and not keep_vault:
            ensure_gitignore_block(path, [], state=ManagedState.ABSENT)
            ensure_gitattributes_block(path, state=ManagedState.ABSENT)
        elif recommended and mdata_before.gitignore_managed:
            ensure_gitignore_block(path, recommended, state=ManagedState.PRESENT)

    action = "dry_run" if dry_run else "uninstall"
    result: dict[str, Any] = {
        "action": action,
        "removed": removed,
        "keep_vault": keep_vault,
        "path": path,
    }
    if errors:
        result["errors"] = errors
    return result


def hooks_list_data() -> dict[str, Any]:
    """Return structured data about all defined hooks.

    Returns:
        A dict with:
        - ``"hooks"``: list of dicts with ``"name"``, ``"enabled"``,
          ``"event"``, ``"actions"`` keys.
        - ``"supported_events"``: sorted list of supported event names.
        - ``"hooks_dir"``: relative path to hooks directory.
    """
    from vaultspec_core.hooks import SUPPORTED_EVENTS, load_hooks

    ctx = _t.get_context()
    hooks = load_hooks(ctx.hooks_dir)
    hooks_data = []
    for hook in hooks:
        actions = ", ".join(a.command for a in hook.actions if a.action_type == "shell")
        hooks_data.append(
            {
                "name": hook.name,
                "enabled": hook.enabled,
                "event": hook.event,
                "actions": actions,
            }
        )

    try:
        rel = str(ctx.hooks_dir.relative_to(ctx.target_dir))
    except ValueError:
        # HOOKS_DIR may live in the CWD workspace, not under TARGET_DIR,
        # when --target points to a separate directory.
        rel = str(ctx.hooks_dir)
    return {
        "hooks": hooks_data,
        "supported_events": sorted(SUPPORTED_EVENTS),
        "hooks_dir": rel,
    }


def hooks_run(event: str, path: str | None = None) -> list[dict[str, Any]]:
    """Trigger hooks for an event.

    Returns:
        A list of result dicts with ``"hook_name"``, ``"action_type"``,
        ``"success"``, ``"output"``, ``"error"`` keys.

    Raises:
        ProviderError: If the event is not in SUPPORTED_EVENTS.
    """
    from vaultspec_core.hooks import SUPPORTED_EVENTS, load_hooks, trigger

    if event not in SUPPORTED_EVENTS:
        raise ProviderError(
            f"Unknown event: {event}. Supported: {', '.join(sorted(SUPPORTED_EVENTS))}"
        )

    ws_ctx = _t.get_context()
    hooks = load_hooks(ws_ctx.hooks_dir)
    matching = [h for h in hooks if h.event == event and h.enabled]
    if not matching:
        logger.info("No enabled hooks for event: %s", event)
        return []

    ctx = {"root": str(ws_ctx.target_dir), "event": event}
    if path:
        ctx["path"] = path

    logger.info("Triggering %d hook(s) for '%s'...", len(matching), event)
    results = trigger(hooks, event, ctx)
    return [
        {
            "hook_name": r.hook_name,
            "action_type": r.action_type,
            "success": r.success,
            "output": r.output,
            "error": r.error,
        }
        for r in results
    ]


# Valid sync provider targets exposed to the CLI.
SYNC_PROVIDERS = VALID_PROVIDERS - {"core"}


def sync_provider(
    provider: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    skip: set[str] | None = None,
) -> list[_t.SyncResult]:
    """Sync resources for a single provider target.

    ``provider`` must be one of :data:`SYNC_PROVIDERS`.  The special value
    ``"all"`` syncs every provider and fires post-sync hooks.

    When *force* is ``True``, stale destination files are pruned and
    user-authored system/config files are overwritten.  When ``False``
    (the default), the sync is additive-only and any divergences are
    reported as warnings on the returned :class:`SyncResult` objects.

    Args:
        provider: Provider target to sync.
        dry_run: Preview changes without writing.
        force: Prune stale files and overwrite user-authored content.
        skip: Set of provider names to exclude from the sync.

    Returns:
        A list of :class:`SyncResult` objects from each sync pass.

    Raises:
        ProviderError: If *provider* is invalid.
        WorkspaceNotInitializedError: If ``.vaultspec/`` does not exist.
        ProviderNotInstalledError: If the specified provider is not installed.
    """
    if provider not in SYNC_PROVIDERS:
        raise ProviderError(
            f"Unknown sync target '{provider}'. "
            f"Valid: {', '.join(sorted(SYNC_PROVIDERS))}"
        )

    skip = _validate_skip(skip, allow_core=False)

    from .agents import agents_sync
    from .config_gen import config_sync
    from .mcps import mcp_sync as _mcp_sync
    from .rules import rules_sync
    from .skills import skills_sync
    from .system import system_sync

    ctx = _t.get_context()

    def _empty_sync_results() -> list[_t.SyncResult]:
        return [_t.SyncResult() for _ in range(5)]

    def _backfill_structures() -> _t.SyncResult:
        """Create missing structural provider directories during sync (#133).

        Content files are backfilled by the per-resource sync passes (their
        ``apply_file_sync`` adds any missing destination), but a content-less
        structural directory such as a provider's ``workflows/`` is only ever
        created by ``install``/``_scaffold_provider``. After an upgrade that
        introduces such a directory, ``sync`` left the provider ``partial``
        while reporting success ("will be addressed by sync") - a no-op. This
        backfill makes that promise real: it creates only directories that are
        missing, never overwriting existing content, so it is safe at every
        ``--force`` level and previews correctly under ``--dry-run``.
        """
        result = _t.SyncResult()
        active_ctx = _t.get_context()
        target = active_ctx.target_dir
        installed = read_manifest_data(target).installed
        for tool, cfg in active_ctx.tool_configs.items():
            # Only backfill providers the operator actually enrolled; never
            # materialise a provider directory a core-only or partial install
            # deliberately omitted.
            if tool.value in skip or tool.value not in installed:
                continue
            caps = cfg.capabilities
            structural: list[Path] = []
            if ProviderCapability.RULES in caps and cfg.rules_dir:
                structural.append(cfg.rules_dir)
            if ProviderCapability.SKILLS in caps and cfg.skills_dir:
                structural.append(cfg.skills_dir)
            if ProviderCapability.AGENTS in caps and cfg.agents_dir:
                structural.append(cfg.agents_dir)
            if ProviderCapability.WORKFLOWS in caps and cfg.workflows_dir:
                structural.append(cfg.workflows_dir)
            for directory in structural:
                if directory.exists():
                    continue
                result.items.append(
                    (_rel(target, directory).replace("\\", "/"), "[ADD]")
                )
                result.added += 1
                if not dry_run:
                    ensure_dir(directory)
        return result

    def _run_all_syncs(*, include_mcp: bool = True) -> list[_t.SyncResult]:
        results: list[_t.SyncResult] = []
        sync_passes: list[tuple[Callable[[], _t.SyncResult], str]] = [
            (lambda: rules_sync(prune=force, dry_run=dry_run), "rules"),
            (lambda: skills_sync(prune=force, dry_run=dry_run), "skills"),
            (lambda: agents_sync(prune=force, dry_run=dry_run), "agents"),
            (lambda: system_sync(dry_run=dry_run, force=force), "system"),
            (lambda: config_sync(dry_run=dry_run, force=force), "config"),
        ]
        if include_mcp and "mcp" not in skip:
            sync_passes.append(
                (
                    lambda: _mcp_sync(dry_run=dry_run, force=force, prune=force),
                    "mcps",
                )
            )
        if "hooks" not in skip:
            from .provider_hooks import provider_hooks_sync

            sync_passes.append((lambda: provider_hooks_sync(dry_run=dry_run), "hooks"))
        for sync_fn, label in sync_passes:
            try:
                results.append(sync_fn())
            except Exception as exc:
                logger.error("Sync pass '%s' failed: %s", label, exc)
                error_result = _t.SyncResult()
                error_result.errors.append(f"{label} sync failed: {exc}")
                results.append(error_result)
        # Structural backfill runs last and is appended after the positional
        # resource passes; renderers treat any result beyond the known pass
        # labels as structural (issue #133).
        results.append(_backfill_structures())
        return results

    # Guard: refuse to sync if vaultspec isn't installed at the target
    vaultspec_dir = ctx.target_dir / ".vaultspec"
    if not vaultspec_dir.exists():
        raise WorkspaceNotInitializedError(
            f"No .vaultspec/ found at {ctx.target_dir}.",
            hint=f"Run 'vaultspec-core install {ctx.target_dir}' first.",
        )

    if provider == "all":
        # When skipping providers, narrow tool_configs in a copied context
        skipped_tools = {Tool(name) for name in skip if name in {t.value for t in Tool}}

        def _sync_all_with_configs(
            narrowed_configs: dict[Tool, _t.ToolConfig] | None,
        ) -> list[_t.SyncResult]:
            if narrowed_configs is not None:
                _t.set_context(replace(ctx, tool_configs=narrowed_configs))
            logger.info("Syncing all resources...")
            results = _run_all_syncs()
            if not dry_run:
                from vaultspec_core.hooks import fire_hooks

                fire_hooks(
                    "config.synced",
                    {"root": str(ctx.target_dir), "event": "config.synced"},
                )
                logger.info("Done.")
            return results

        narrowed_configs: dict[Tool, _t.ToolConfig] | None = None
        if skipped_tools:
            narrowed_configs = {
                k: v for k, v in ctx.tool_configs.items() if k not in skipped_tools
            }

        copied = contextvars.copy_context()
        results = copied.run(_sync_all_with_configs, narrowed_configs)

        if not dry_run:
            import datetime

            from .gitignore import ensure_gitignore_block

            if "precommit" not in skip:
                pc_mdata = read_manifest_data(ctx.target_dir)
                if pc_mdata.precommit_managed:
                    from .diagnosis.collectors import collect_precommit_state
                    from .diagnosis.signals import PrecommitSignal

                    pc_signal = collect_precommit_state(ctx.target_dir)
                    if pc_signal in (
                        PrecommitSignal.NO_HOOKS,
                        PrecommitSignal.NO_FILE,
                    ):
                        pc_mdata.precommit_managed = False
                        write_manifest_data(ctx.target_dir, pc_mdata)
                        logger.info(
                            "Pre-commit hooks removed by user, disabling management"
                        )
                    else:
                        _scaffold_precommit(ctx.target_dir)

            # Respect gitignore opt-out: check whether the user removed
            # the managed block BEFORE re-creating it.  If the block is
            # gone but the manifest still says managed=True, the user
            # opted out -- honour that by flipping the flag.
            mdata = read_manifest_data(ctx.target_dir)
            if mdata.gitignore_managed:
                gi_path = ctx.target_dir / ".gitignore"
                block_present = False
                if gi_path.exists():
                    try:
                        content = gi_path.read_text(encoding="utf-8")
                        begins, ends = _find_markers(content.splitlines())
                        block_present = (
                            len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]
                        )
                    except (OSError, UnicodeDecodeError):
                        block_present = False

                if block_present:
                    ensure_gitignore_block(
                        ctx.target_dir,
                        get_recommended_entries(ctx.target_dir),
                    )
                else:
                    mdata.gitignore_managed = False
                    write_manifest_data(ctx.target_dir, mdata)

            # Respect gitattributes opt-out (same pattern as gitignore).
            mdata = read_manifest_data(ctx.target_dir)
            if mdata.gitattributes_managed:
                ga_path = ctx.target_dir / ".gitattributes"
                ga_block_present = False
                if ga_path.exists():
                    try:
                        content = ga_path.read_text(encoding="utf-8")
                        ga_block_present = _ga_has_valid_block(content.splitlines())
                    except (OSError, UnicodeDecodeError):
                        pass

                if ga_block_present:
                    ensure_gitattributes_block(ctx.target_dir)
                else:
                    mdata.gitattributes_managed = False
                    write_manifest_data(ctx.target_dir, mdata)

            # Update last_synced timestamps for installed providers only
            now = datetime.datetime.now(tz=datetime.UTC).isoformat()
            mdata = read_manifest_data(ctx.target_dir)
            for tool_type in ctx.tool_configs:
                name = tool_type.value
                if name in skip or name not in mdata.installed:
                    continue
                mdata.provider_state.setdefault(name, {})
                mdata.provider_state[name]["last_synced"] = now
            _stamp_manifest_version_no_downgrade(mdata)
            write_manifest_data(ctx.target_dir, mdata)

        return results

    provider_skipped = provider in skip

    # Validate provider is installed unless the provider was explicitly skipped.
    installed = read_manifest(ctx.target_dir)
    if not provider_skipped and installed and provider not in installed:
        raise ProviderNotInstalledError(
            f"Provider '{provider}' is not installed.",
            hint=(
                f"Run 'vaultspec-core install "
                f"--target {ctx.target_dir} {provider}' first."
            ),
        )

    # Per-provider sync: filter tool_configs to only the requested tool.
    requested: set[Tool] = set()
    if not provider_skipped:
        if provider == "claude":
            requested = {Tool.CLAUDE}
        elif provider == "gemini":
            requested = {Tool.GEMINI}
        elif provider == "antigravity":
            requested = {Tool.ANTIGRAVITY}
        elif provider == "codex":
            requested = {Tool.CODEX}
    else:
        return _empty_sync_results()

    def _sync_single_provider(
        provider_configs: dict[Tool, _t.ToolConfig],
    ) -> list[_t.SyncResult]:
        _t.set_context(replace(ctx, tool_configs=provider_configs))
        logger.info("Syncing provider: %s ...", provider)
        results = _run_all_syncs(include_mcp=False)
        if not dry_run:
            logger.info("Done.")
        return results

    narrowed = {k: v for k, v in ctx.tool_configs.items() if k in requested}
    copied = contextvars.copy_context()
    results = copied.run(_sync_single_provider, narrowed)

    if not dry_run:
        import datetime

        now = datetime.datetime.now(tz=datetime.UTC).isoformat()
        mdata = read_manifest_data(ctx.target_dir)
        for tool_type in requested:
            name = tool_type.value
            if name not in mdata.installed:
                continue
            mdata.provider_state.setdefault(name, {})
            mdata.provider_state[name]["last_synced"] = now
        _stamp_manifest_version_no_downgrade(mdata)
        write_manifest_data(ctx.target_dir, mdata)

    return results
