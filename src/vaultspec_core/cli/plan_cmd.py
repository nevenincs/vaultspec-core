"""Typer wiring for ``vaultspec-core vault plan ...`` subcommand group.

Registers the read commands (``status``, ``check``, ``query``) and the
container-level mutating verbs (``step``/``phase``/``wave`` add/insert/
move/edit/check/uncheck/toggle/edit/remove, ``epic intent``, ``tier``).

Each command is a thin Typer wrapper over the pure-Python handlers in
:mod:`vaultspec_core.plan` and :mod:`vaultspec_core.plan.commands`. The
wrapper parses CLI arguments, opens the plan file, dispatches the
handler, serialises back to disk, and emits the appropriate human or
JSON output.

This module is the public surface for the ``plan`` command group: the Typer
app instances and every command implementation live in sibling modules,
split along container seams (:mod:`.plan_cmd_read`, :mod:`.plan_cmd_step`,
:mod:`.plan_cmd_phase`, :mod:`.plan_cmd_wave`, :mod:`.plan_cmd_epic`,
:mod:`.plan_cmd_tier`, :mod:`.plan_cmd_trailer`) plus a shared-helper module
(:mod:`.plan_cmd_shared`) and the app-instance module (:mod:`.plan_cmd_app`).
Importing this module registers every command onto :data:`plan_app` and
re-exports the full prior public surface so no import site outside this
package needs to change.
"""

# Each sibling module defines its own Typer app (mounted explicitly in
# .plan_cmd_app) and registers its commands as an import-time side effect;
# importing them here, in the original definition order, reproduces the
# original --help listing order regardless of how isort/ruff would otherwise
# alphabetize these imports. The names pulled in here are re-exported for
# compatibility with call sites that imported them directly from this
# module (the Typer app instances, the shared plan-write helpers, and every
# command function).
from vaultspec_core.cli.plan_cmd_app import (
    epic_app,
    phase_app,
    plan_app,
    step_app,
    tier_app,
    trailer_app,
    wave_app,
)
from vaultspec_core.cli.plan_cmd_epic import (
    cmd_epic_intent_edit,
    cmd_epic_intent_show,
    epic_intent_app,
)
from vaultspec_core.cli.plan_cmd_phase import (
    cmd_phase_add,
    cmd_phase_edit,
    cmd_phase_insert,
    cmd_phase_move,
    cmd_phase_remove,
    cmd_phase_renumber,
)
from vaultspec_core.cli.plan_cmd_read import cmd_check, cmd_query, cmd_status
from vaultspec_core.cli.plan_cmd_shared import (
    emit_plan_mutation_json,
    invalidate_graph_cache_for_plan,
    render_user_errors,
    resolve_vault_root,
    save_plan_or_dry_run,
)
from vaultspec_core.cli.plan_cmd_step import (
    cmd_step_add,
    cmd_step_check,
    cmd_step_edit,
    cmd_step_insert,
    cmd_step_move,
    cmd_step_remove,
    cmd_step_toggle,
    cmd_step_uncheck,
)
from vaultspec_core.cli.plan_cmd_tier import (
    cmd_tier_demote,
    cmd_tier_promote,
    cmd_tier_show,
)
from vaultspec_core.cli.plan_cmd_trailer import cmd_trailer_emit, cmd_trailer_validate
from vaultspec_core.cli.plan_cmd_wave import (
    cmd_wave_add,
    cmd_wave_edit,
    cmd_wave_insert,
    cmd_wave_move,
    cmd_wave_remove,
)

__all__ = [
    "cmd_check",
    "cmd_epic_intent_edit",
    "cmd_epic_intent_show",
    "cmd_phase_add",
    "cmd_phase_edit",
    "cmd_phase_insert",
    "cmd_phase_move",
    "cmd_phase_remove",
    "cmd_phase_renumber",
    "cmd_query",
    "cmd_status",
    "cmd_step_add",
    "cmd_step_check",
    "cmd_step_edit",
    "cmd_step_insert",
    "cmd_step_move",
    "cmd_step_remove",
    "cmd_step_toggle",
    "cmd_step_uncheck",
    "cmd_tier_demote",
    "cmd_tier_promote",
    "cmd_tier_show",
    "cmd_trailer_emit",
    "cmd_trailer_validate",
    "cmd_wave_add",
    "cmd_wave_edit",
    "cmd_wave_insert",
    "cmd_wave_move",
    "cmd_wave_remove",
    "emit_plan_mutation_json",
    "epic_app",
    "epic_intent_app",
    "invalidate_graph_cache_for_plan",
    "phase_app",
    "plan_app",
    "render_user_errors",
    "resolve_vault_root",
    "save_plan_or_dry_run",
    "step_app",
    "tier_app",
    "trailer_app",
    "wave_app",
]
