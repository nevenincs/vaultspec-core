"""Shared Typer app instances for the ``vaultspec-core vault`` command family.

Defines :data:`vault_app`, the parent Typer group for ``vaultspec-core vault``,
and its sub-apps (:data:`feature_app`, :data:`check_app`, :data:`sanitize_app`,
:data:`rule_app`, :data:`adr_app`). Split out from
:mod:`vaultspec_core.cli.vault_cmd` so the per-verb command modules can import
and mount onto these apps without a circular import back through
:mod:`vaultspec_core.cli.vault_cmd`, which re-exports them as the public
surface.

This mirrors :mod:`vaultspec_core.cli.plan_cmd_app` and
:mod:`vaultspec_core.cli.spec_cmd_app`. The ``vault`` family was the last one
without such a module, and its absence is what produced the two workarounds
this module removes: ``vault_cmd`` imported its command modules at the *bottom*
of the file under ``# noqa: E402`` to break the cycle, and those modules in turn
nested every command inside a ``register_*(app)`` function so the app could be
passed in as a parameter. That nesting made each command a closure that nothing
calls, which ``basedpyright`` correctly reported as
``reportUnusedFunction`` - answered by 32 inline ``# pyright: ignore``
comments, against a project convention that bans them (stated in
``dev/guards/test_automation_contracts.py``).

Owning the apps here lets the command modules decorate at module level, exactly
as :mod:`vaultspec_core.cli.plan_cmd_wave` and its siblings already do, so the
suppressions stop being necessary rather than being silenced.

Three ``# noqa: E402`` markers deliberately survive in
:mod:`vaultspec_core.cli.vault_cmd`, on the ``link``, ``exec`` and ``archive``
sub-app mounts. They are not leftovers. Ruff's preamble allowance means the
first cross-family mount (``plan``) needs no marker, while the ``add_typer``
call after it ends the preamble, so the next three do.

Those four mounts could be moved here to retire all three markers - the target
modules have no import edge back, and appending them after the ``adr`` mount
would preserve the group order exactly. They are not, because this module is a
leaf of the CLI import graph: it imports :mod:`vaultspec_core.cli._app` and
nothing else, which is what lets every command module import it without any
possibility of a cycle. Importing four command families here would make it the
package's heaviest importer and put the module that every command module
depends on downstream of them - the shape that produced the cycle this module
exists to remove. That layering is worth more than three suppressions ruff
itself considers legitimate.

Note this is an argument about the import *graph*, not about what a process
loads: ``cli/__init__.py`` does ``from .root import app``, so importing any
module in this package already builds the whole CLI.
"""

from __future__ import annotations

from vaultspec_core.cli._app import make_app

__all__ = [
    "adr_app",
    "check_app",
    "feature_app",
    "rule_app",
    "sanitize_app",
    "vault_app",
]

vault_app = make_app(
    help="Create, query, and audit records in the .vault/ project history.",
    no_args_is_help=True,
)

feature_app = make_app(
    help="Manage vault feature tags",
    no_args_is_help=True,
)
vault_app.add_typer(feature_app, name="feature")

check_app = make_app(
    help="Run vault health checks with optional auto-fix",
    no_args_is_help=True,
)
vault_app.add_typer(check_app, name="check")

sanitize_app = make_app(
    help="Run explicit vault sanitizers",
    no_args_is_help=True,
)
vault_app.add_typer(sanitize_app, name="sanitize")

rule_app = make_app(
    help="Manage custom team-shared rules",
    no_args_is_help=True,
)
vault_app.add_typer(rule_app, name="rule")

adr_app = make_app(
    help="Manage Architecture Decision Records (ADRs)",
    no_args_is_help=True,
)
vault_app.add_typer(adr_app, name="adr")
