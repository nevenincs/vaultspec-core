"""The shared ``spec`` Typer app instance.

Defines :data:`spec_app`, the parent Typer group for the ``vaultspec-core
spec`` command family. Split out from :mod:`vaultspec_core.cli.spec_cmd` so
the per-resource command modules (rules, skills, agents, system, hooks,
mcps, doctor, reference) can import and mount onto it without a circular
import back through :mod:`vaultspec_core.cli.spec_cmd`, which re-exports
this module's :data:`spec_app` as the public surface.
"""

from vaultspec_core.cli._app import make_app

spec_app = make_app(
    help=(
        "Manage framework resources: rules, skills, agents, system prompts, hooks, "
        "and MCPs."
    ),
    no_args_is_help=True,
)
