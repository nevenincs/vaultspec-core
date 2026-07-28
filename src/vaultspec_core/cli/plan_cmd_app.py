"""Shared Typer app instances for the ``vaultspec-core vault plan`` command family.

Defines :data:`plan_app`, the parent Typer group for
``vaultspec-core vault plan``, and its container-scoped sub-apps
(:data:`step_app`, :data:`phase_app`, :data:`wave_app`, :data:`epic_app`,
:data:`tier_app`, :data:`trailer_app`). Split out from
:mod:`vaultspec_core.cli.plan_cmd` so the per-container command modules can
import and mount onto these apps without a circular import back through
:mod:`vaultspec_core.cli.plan_cmd`, which re-exports them as the public
surface.
"""

from vaultspec_core.cli._app import make_app

plan_app = make_app(
    help="Plan-document inspection and manipulation per the plan-hardening convention",
    no_args_is_help=True,
)

step_app = make_app(
    help=(
        "Step-level operations "
        "(add / insert / move / remove / check / uncheck / toggle / edit)."
    ),
    no_args_is_help=True,
)
plan_app.add_typer(step_app, name="step")

phase_app = make_app(
    help="Phase-level operations (add / insert / move / remove / edit)",
    no_args_is_help=True,
)
plan_app.add_typer(phase_app, name="phase")

wave_app = make_app(
    help="Wave-level operations (add / insert / move / remove / edit)",
    no_args_is_help=True,
)
plan_app.add_typer(wave_app, name="wave")

epic_app = make_app(
    help="Epic-level operations (intent show / edit; L4 only)",
    no_args_is_help=True,
)
plan_app.add_typer(epic_app, name="epic")

tier_app = make_app(
    help="Tier inspection and promotion / demotion",
    no_args_is_help=True,
)
plan_app.add_typer(tier_app, name="tier")

trailer_app = make_app(
    help=(
        "Commit-linkage trailers: emit a well-formed trailer, or validate "
        "the trailers in a commit message (advisory; always exits 0)."
    ),
    no_args_is_help=True,
)
plan_app.add_typer(trailer_app, name="trailer")
