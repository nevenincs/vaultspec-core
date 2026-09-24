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
from .git_artifacts import (
    check_staged_provider_artifacts,
    untrack_managed_paths,
)
from .install_mode import (
    fresh_install_schema_version,
    infer_upgrade_mode,
    persist_resolved_mode,
    stamp_manifest_version_no_downgrade,
)
from .precommit import (
    CANONICAL_ENTRY_PREFIX,
    CANONICAL_HOOK_ENTRIES,
    CANONICAL_HOOK_IDS,
    CANONICAL_PRECOMMIT_HOOKS,
    canonical_hook_entries_for_mode,
    canonical_precommit_hooks_for_mode,
    entry_prefix_for_mode,
    hook_defs_for_mode,
    scaffold_precommit,
)
from .provider_registry import (
    PROVIDER_TO_TOOLS,
    SYNC_PROVIDERS,
    VALID_PROVIDERS,
    filter_tools,
    rel,
    require_reconciliation_success,
    validate_provider,
    validate_skip,
)
from .provider_sync import sync_provider
from .provision import ensure_tool_configs, init_run, install_run
from .scaffold import scaffold_core, scaffold_provider
from .uninstall import uninstall_run

logger = logging.getLogger(__name__)

__all__ = [
    "CANONICAL_ENTRY_PREFIX",
    "CANONICAL_HOOK_ENTRIES",
    "CANONICAL_HOOK_IDS",
    "CANONICAL_PRECOMMIT_HOOKS",
    "PROVIDER_TO_TOOLS",
    "SYNC_PROVIDERS",
    "VALID_PROVIDERS",
    "canonical_hook_entries_for_mode",
    "canonical_precommit_hooks_for_mode",
    "check_staged_provider_artifacts",
    "ensure_tool_configs",
    "entry_prefix_for_mode",
    "filter_tools",
    "fresh_install_schema_version",
    "hook_defs_for_mode",
    "infer_upgrade_mode",
    "init_run",
    "install_run",
    "persist_resolved_mode",
    "rel",
    "require_reconciliation_success",
    "scaffold_core",
    "scaffold_precommit",
    "scaffold_provider",
    "stamp_manifest_version_no_downgrade",
    "sync_provider",
    "uninstall_run",
    "untrack_managed_paths",
    "validate_provider",
    "validate_skip",
]


def triggers_list_data() -> dict[str, Any]:
    """Return structured data about all defined lifecycle triggers.

    Returns:
        A dict with:
        - ``"triggers"``: list of dicts with ``"name"``, ``"enabled"``,
          ``"event"``, ``"actions"``, ``"trusted"`` keys.
        - ``"supported_events"``: sorted list of supported event names.
        - ``"triggers_dir"``: relative path to the triggers directory.
    """
    from vaultspec_core.triggers import SUPPORTED_EVENTS, is_trusted, load_triggers

    ctx = _t.get_context()
    triggers = load_triggers(ctx.triggers_dir)
    triggers_data: list[dict[str, Any]] = []
    for trig in triggers:
        actions = ", ".join(a.command for a in trig.actions if a.action_type == "shell")
        triggers_data.append(
            {
                "name": trig.name,
                "enabled": trig.enabled,
                "event": trig.event,
                "actions": actions,
                # An enabled trigger that is not trusted never runs. Reporting
                # the two flags separately is what stops "enabled" from reading
                # as "will run" and turning a refusal into a mystery.
                "trusted": is_trusted(trig.source_path),
            }
        )

    try:
        rel = str(ctx.triggers_dir.relative_to(ctx.target_dir))
    except ValueError:
        # The triggers directory may live in the CWD workspace, not under
        # TARGET_DIR, when --target points to a separate directory.
        rel = str(ctx.triggers_dir)
    return {
        "triggers": triggers_data,
        "supported_events": sorted(SUPPORTED_EVENTS),
        "triggers_dir": rel,
    }


def triggers_run(event: str, path: str | None = None) -> list[dict[str, Any]]:
    """Trigger hooks for an event.

    Returns:
        A list of result dicts with ``"trigger_name"``, ``"action_type"``,
        ``"success"``, ``"output"``, ``"error"`` keys.

    Raises:
        ProviderError: If the event is not in SUPPORTED_EVENTS.
    """
    from vaultspec_core.triggers import SUPPORTED_EVENTS, load_triggers
    from vaultspec_core.triggers.engine import fire

    from .exceptions import ProviderError

    if event not in SUPPORTED_EVENTS:
        raise ProviderError(
            f"Unknown event: {event}. Supported: {', '.join(sorted(SUPPORTED_EVENTS))}"
        )

    ws_ctx = _t.get_context()
    hooks = load_triggers(ws_ctx.triggers_dir)
    matching = [h for h in hooks if h.event == event and h.enabled]
    if not matching:
        logger.info("No enabled hooks for event: %s", event)
        return []

    ctx = {"root": str(ws_ctx.target_dir), "event": event}
    if path:
        ctx["path"] = path

    logger.info("Triggering %d hook(s) for '%s'...", len(matching), event)
    results = fire(hooks, event, ctx)
    return [
        {
            "trigger_name": r.trigger_name,
            "action_type": r.action_type,
            "success": r.success,
            "output": r.output,
            "error": r.error,
        }
        for r in results
    ]
