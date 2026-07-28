"""Render and reconcile vaultspec-core's managed pre-commit hooks.

Covers the mode-parameterized canonical hook definitions (entry prefix, hook
metadata, and the derived canonical hook list/entry map) plus the
``.pre-commit-config.yaml`` scaffolding and stripping logic that keeps a
project's hook file in sync with them.
"""

from __future__ import annotations

import io
import logging
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML, YAMLError

from .enums import InstallMode, PrecommitHook, render_mode
from .helpers import advisory_lock, atomic_write
from .prek_boundary import collect_prek_boundary

logger = logging.getLogger(__name__)

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
    """Return the canonical hook-entry command prefix for *mode*.

    The lookup is keyed by the *rendered* mode (via
    :func:`~vaultspec_core.core.enums.render_mode`), so
    :attr:`~vaultspec_core.core.enums.InstallMode.DEV` resolves to the same
    ``uv run`` prefix as :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY`
    rather than needing its own table entry. This keeps the prefix table a
    two-shape render surface even as the mode vocabulary carries the third
    dev-scoped bookkeeping member.
    """
    return _MODE_ENTRY_PREFIX[render_mode(mode)]


#: Backward-compatible module-level prefix, pinned to dependency mode. Modules
#: and diagnostics that still assume a single prefix (the doctor's
#: canonical-entry check) read this until they are made mode-aware; the
#: mode-parameterized renderers derive their prefix from
#: :func:`entry_prefix_for_mode` instead.
CANONICAL_ENTRY_PREFIX = entry_prefix_for_mode(InstallMode.DEPENDENCY)


# Mode-independent pre-commit hook metadata: the CLI subcommand each hook
# invokes plus its non-entry pre-commit fields. The ``entry`` is derived per
# mode by prefixing the subcommand with the mode's canonical entry prefix. The
# insertion order here is the order hooks are scaffolded into
# ``.pre-commit-config.yaml`` and must be preserved.
_HOOK_SUBCOMMAND: dict[PrecommitHook, str] = {
    PrecommitHook.VAULT_FIX: "vault check all --fix",
    PrecommitHook.VAULT_SANITIZE_ANNOTATIONS: "vault sanitize annotations",
    PrecommitHook.CHECK_PROVIDER_ARTIFACTS: "check-providers",
    # ``--gate-errors`` folds the doctor's warning exit (1) to 0 so the gate
    # blocks only on errors. Warning-level provider-mirror lag is the expected
    # steady state after any builtins change - check-provider-artifacts forbids
    # committing the regenerated mirror - so a warning-strict gate would
    # deadlock every commit. This is the canonical entry, not a hand-hardened
    # local override, so sync renders it directly rather than clobbering it.
    PrecommitHook.SPEC_CHECK: "spec doctor --gate-errors",
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


def _precommit_yaml() -> YAML:
    """Return a round-trip YAML handler for ``.pre-commit-config.yaml``.

    Round-trip mode preserves the parts of an author-maintained config that a
    plain ``safe_load`` + ``dump`` cycle would silently rewrite: explanatory
    comments, the single-quoted literal form of ``exclude``/``files`` regexes,
    and long ``entry`` scalars that a re-emitter would otherwise line-wrap.
    Preserving them is what makes a full ``sync`` over a correctly-rendered
    config a byte-for-byte no-op instead of a spurious diff.

    The sequence indent is pinned to the non-indented block style
    (``sequence=2, offset=0``) so a freshly scaffolded config matches the
    historical layout, and ``width`` is raised so entry scalars are never
    folded onto continuation lines.
    """
    handler = YAML()
    handler.preserve_quotes = True
    handler.width = 4096
    handler.indent(mapping=2, sequence=2, offset=0)
    return handler


def _dump_precommit_yaml(handler: YAML, data: object) -> str:
    """Serialise *data* to a string through the round-trip *handler*."""
    buffer = io.StringIO()
    handler.dump(data, buffer)
    return buffer.getvalue()


def _drop_managed_hook_entries(repos: list[Any]) -> bool:
    """Delete vaultspec-managed hooks from the ``repos`` sequence in place.

    Mutates the loaded structure so surviving non-vaultspec hooks keep their
    comments and quoting, and drops any local repo left without hooks.

    Returns:
        ``True`` when a managed hook was deleted.
    """
    changed = False
    for r in list(repos):
        if not (isinstance(r, dict) and r.get("repo") == "local"):
            continue
        hooks = r.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        managed_idx = [
            i
            for i, h in enumerate(hooks)
            if isinstance(h, dict) and h.get("id") in _ALL_MANAGED_HOOK_IDS
        ]
        for i in reversed(managed_idx):
            del hooks[i]
        if managed_idx:
            changed = True
        if not hooks:
            repos.remove(r)
    return changed


def _strip_managed_precommit_hooks(config_file: Path) -> bool:
    """Remove vaultspec-managed hooks from an existing ``.pre-commit-config.yaml``.

    The file is rewritten in place, or deleted when nothing but the managed
    hooks remained.  Read, parse, and write failures are absorbed: uninstall
    residue removal is best-effort and never fails the run.

    Returns:
        ``True`` when the config was rewritten or deleted.
    """
    handler = _precommit_yaml()
    try:
        data = handler.load(config_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        repos = data.get("repos", [])
        if not isinstance(repos, list):
            return False
        if not _drop_managed_hook_entries(repos):
            return False

        if repos:
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
            return True
        del data["repos"]
        if data:
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
        else:
            config_file.unlink()
    except (YAMLError, OSError):
        return False
    return True


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

    Skips scaffolding entirely when ``prek.toml`` is present at *target*
    (assessed through
    :func:`~vaultspec_core.core.prek_boundary.collect_prek_boundary`):
    prek reads ``prek.toml`` exclusively and silently ignores a co-present
    ``.pre-commit-config.yaml``, so writing the YAML would leave hooks prek
    never runs. The operator transplants hooks into ``prek.toml`` with
    ``spec precommit migrate``; the log messages distinguish a healthy
    transplant (hooks already in ``prek.toml``) from stranded hooks.
    """
    if mode is None:
        from .workspace_mode import CORE_DISTRIBUTION_NAME, resolve_render_mode

        mode = resolve_render_mode(target, package=CORE_DISTRIBUTION_NAME)
    canonical_hooks = canonical_precommit_hooks_for_mode(mode)

    boundary = collect_prek_boundary(target, mode=mode)
    if boundary.owns_boundary:
        if boundary.hooks_present:
            logger.info(
                "prek.toml at %s already carries the vaultspec-core hooks; "
                "skipping .pre-commit-config.yaml scaffold.",
                target,
            )
            if (target / ".pre-commit-config.yaml").exists():
                logger.info(
                    "A superseded .pre-commit-config.yaml is still present at %s. "
                    "prek reads prek.toml exclusively; remove the YAML config "
                    "once nothing else consumes it.",
                    target,
                )
        else:
            logger.info(
                "prek.toml detected at %s; skipping .pre-commit-config.yaml "
                "scaffold. Run 'vaultspec-core spec precommit migrate' to "
                "transplant the vaultspec-core hooks into prek.toml.",
                target,
            )
            if (target / ".pre-commit-config.yaml").exists():
                logger.warning(
                    "Both prek.toml and .pre-commit-config.yaml are present at "
                    "%s and prek.toml lacks the vaultspec-core hooks. prek "
                    "reads prek.toml exclusively; vaultspec will not refresh "
                    "the YAML hooks. Run 'vaultspec-core spec precommit "
                    "migrate' to transplant them.",
                    target,
                )
        return []

    config_file = target / ".pre-commit-config.yaml"
    handler = _precommit_yaml()

    with nullcontext() if dry_run else advisory_lock(config_file):
        if config_file.exists():
            try:
                raw = config_file.read_text(encoding="utf-8")
                data = handler.load(raw) or {}
                if not isinstance(data, dict):
                    return []
            except (YAMLError, OSError):
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
                    existing = existing_by_id.get(hook_id)
                    if existing is None:
                        existing_hooks.append(dict(canonical))
                        logger.info("Added pre-commit hook '%s'", str(canonical["id"]))
                        changed = True
                        continue
                    if existing.get("entry") == canonical["entry"]:
                        continue
                    existing["entry"] = canonical["entry"]
                    logger.info(
                        "Updated pre-commit hook '%s' entry to canonical pattern",
                        hook_id,
                    )
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
                atomic_write(config_file, _dump_precommit_yaml(handler, data))
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
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
        return [(".pre-commit-config.yaml", "precommit")]
