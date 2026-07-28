"""Implement the top-level operational commands mounted into the root CLI.

This module contains the business logic behind workspace initialization,
install, uninstall, and sync. It sits above the lower-level resource-management
modules and provides the user-facing command behaviors that do not belong
to a dedicated nested Typer namespace.

The implementation is split across sibling modules by concern (provider
vocabulary and validation, provisioning-mode resolution, directory
scaffolding, pre-commit hook rendering, git-artifact bookkeeping, install and
uninstall orchestration, and provider sync). This module re-exports every
name those siblings define so it remains the single public import surface:
callers should keep importing from ``vaultspec_core.core.commands`` regardless
of which sibling module actually implements a given name.
"""

from __future__ import annotations

import logging
from typing import Any

from . import types as _t
from .git_artifacts import (  # noqa: F401
    _UNTRACK_PREFIXES,
    PROVIDER_ARTIFACT_PATTERNS,
    _has_gitattributes_block,
    _has_gitignore_block,
    _is_git_repo,
    _untrack_managed_paths,
    check_staged_provider_artifacts,
)
from .install_mode import (  # noqa: F401
    _fresh_install_schema_version,
    _infer_upgrade_mode,
    _persist_resolved_mode,
    _stamp_manifest_version_no_downgrade,
    _write_mode_declaration,
)
from .precommit import (  # noqa: F401
    _ALL_MANAGED_HOOK_IDS,
    _HOOK_META,
    _HOOK_SUBCOMMAND,
    _MODE_ENTRY_PREFIX,
    CANONICAL_ENTRY_PREFIX,
    CANONICAL_HOOK_ENTRIES,
    CANONICAL_HOOK_IDS,
    CANONICAL_PRECOMMIT_HOOKS,
    _drop_managed_hook_entries,
    _dump_precommit_yaml,
    _precommit_yaml,
    _scaffold_precommit,
    _strip_managed_precommit_hooks,
    canonical_hook_entries_for_mode,
    canonical_precommit_hooks_for_mode,
    entry_prefix_for_mode,
    hook_defs_for_mode,
)
from .provider_registry import (  # noqa: F401
    _PROVIDER_TO_TOOLS,
    SYNC_PROVIDERS,
    VALID_PROVIDERS,
    _filter_tools,
    _rel,
    _require_reconciliation_success,
    _validate_provider,
    _validate_skip,
)
from .provider_sync import (  # noqa: F401
    _SYNC_PROVIDER_TOOLS,
    _backfill_structures,
    _empty_sync_results,
    _mcp_sync_pass,
    _reconcile_gitattributes_opt_out,
    _reconcile_gitignore_opt_out,
    _reconcile_precommit_management,
    _run_all_syncs,
    _stamp_last_synced,
    _sync_all_providers,
    sync_provider,
)
from .provision import (  # noqa: F401
    _detect_precommit_managed,
    _ensure_tool_configs,
    _finalize_upgrade_manifest,
    _migrate_mcp_launch_shape,
    _preview_install_manifest,
    _preview_mcp_targets,
    _preview_upgrade_items,
    _reseed_builtins,
    _run_upgrade,
    init_run,
    install_run,
)
from .scaffold import _scaffold_core, _scaffold_provider  # noqa: F401
from .uninstall import (  # noqa: F401
    _UNINSTALL_DIR_LABELS,
    _UNINSTALL_DIR_OWNERS,
    _UNINSTALL_FILE_LABELS,
    _UNINSTALL_FILE_OWNERS,
    _delete_managed_dir,
    _delete_managed_file,
    _reconcile_uninstall_git_blocks,
    _uninstall_everything,
    _uninstall_mcp_targets,
    _uninstall_precommit_hooks,
    _uninstall_provider_artifacts,
    uninstall_run,
)

logger = logging.getLogger(__name__)


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

    from .exceptions import ProviderError

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
