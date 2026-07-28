"""Spec command group  - manage framework resources in ``.vaultspec/``.

Sub-groups: ``vaultspec-core spec rules`` (:data:`rules_app`),
``vaultspec-core spec skills`` (:data:`skills_app`),
``vaultspec-core spec agents`` (:data:`agents_app`),
``vaultspec-core spec system`` (:data:`system_app`),
``vaultspec-core spec hooks`` (:data:`hooks_app`), and
``vaultspec-core spec mcps`` (:data:`mcps_app`).
Top-level command: ``vaultspec-core spec doctor`` for workspace health diagnosis.
Delegates to :mod:`vaultspec_core.core`
CRUD functions via lazy imports to avoid circular-import issues. Mounted onto
:data:`.root.app` as the ``spec`` command group.

This module is the public surface for the ``spec`` command group: the Typer
app instance and every command implementation live in sibling modules,
split along resource-group seams (:mod:`.spec_cmd_rules`,
:mod:`.spec_cmd_skills`, :mod:`.spec_cmd_agents`, :mod:`.spec_cmd_system`,
:mod:`.spec_cmd_hooks`, :mod:`.spec_cmd_mcps`, :mod:`.spec_cmd_doctor`,
:mod:`.spec_cmd_reference`) plus a shared-helper module
(:mod:`.spec_cmd_shared`). Importing this module registers every command
onto :data:`spec_app` and re-exports the full prior public surface so no
import site outside this package needs to change.
"""

# Each sibling module defines its own Typer app (or, for doctor, a plain
# command function); mounting them onto ``spec_app`` happens explicitly
# below. The names pulled in here are re-exported for compatibility with
# call sites that imported them directly from this module.
from vaultspec_core.cli.spec_cmd_agents import agents_app
from vaultspec_core.cli.spec_cmd_app import spec_app
from vaultspec_core.cli.spec_cmd_doctor import (
    _doctor_exit_code,
    _gate,
    _provider_status,
    _render_diagnosis_table,
    _signal_status,
    cmd_doctor,
    logger,
)
from vaultspec_core.cli.spec_cmd_hooks import hooks_app, precommit_app
from vaultspec_core.cli.spec_cmd_mcps import mcps_app
from vaultspec_core.cli.spec_cmd_reference import reference_app
from vaultspec_core.cli.spec_cmd_rules import rules_app
from vaultspec_core.cli.spec_cmd_shared import (
    COMPLETE_SYNC_COMMAND,
    PROVIDER_OUTPUTS,
    _apply_provider_filter,
    _emit_json,
    _emit_sync_result,
    _print_complete_sync_notice,
    _print_source_mutation_notice,
    _resource_path,
    _restore_resource_command,
    _run_edit_command,
    _spec_status_command,
)
from vaultspec_core.cli.spec_cmd_skills import skills_app
from vaultspec_core.cli.spec_cmd_system import system_app

# Mount every sub-app and command explicitly, in the original definition
# order (rules, skills, agents, system, hooks, precommit, mcps, doctor,
# reference) rather than relying on import order, which isort/ruff would
# otherwise alphabetize and so silently reorder the generated CLI
# reference and the ``--help`` command listing.
spec_app.add_typer(rules_app, name="rules")
spec_app.add_typer(skills_app, name="skills")
spec_app.add_typer(agents_app, name="agents")
spec_app.add_typer(system_app, name="system")
spec_app.add_typer(hooks_app, name="hooks")
spec_app.add_typer(precommit_app, name="precommit")
spec_app.add_typer(mcps_app, name="mcps")
spec_app.command("doctor")(cmd_doctor)
spec_app.add_typer(reference_app, name="reference")

__all__ = [
    "COMPLETE_SYNC_COMMAND",
    "PROVIDER_OUTPUTS",
    "_apply_provider_filter",
    "_doctor_exit_code",
    "_emit_json",
    "_emit_sync_result",
    "_gate",
    "_print_complete_sync_notice",
    "_print_source_mutation_notice",
    "_provider_status",
    "_render_diagnosis_table",
    "_resource_path",
    "_restore_resource_command",
    "_run_edit_command",
    "_signal_status",
    "_spec_status_command",
    "agents_app",
    "cmd_doctor",
    "hooks_app",
    "logger",
    "mcps_app",
    "precommit_app",
    "reference_app",
    "rules_app",
    "skills_app",
    "spec_app",
    "system_app",
]
