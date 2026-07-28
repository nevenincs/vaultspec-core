"""Commit-linkage trailer ``vault plan trailer`` commands: emit / validate.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.trailer_app`. Split out
of :mod:`vaultspec_core.cli.plan_cmd`; unlike the container-level mutators,
these commands never touch a plan file (``emit`` prints a formatted line,
``validate`` inspects a commit-message file), so they carry no ``--dry-run``
/ ``--canonicalise`` plumbing.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

from vaultspec_core.cli.plan_cmd_app import trailer_app
from vaultspec_core.cli.plan_cmd_shared import _render_user_errors

__all__ = ["cmd_trailer_emit", "cmd_trailer_validate"]


@trailer_app.command("emit")
@_render_user_errors
def cmd_trailer_emit(
    step: Annotated[
        str | None,
        typer.Option(
            "--step",
            help="Step or Phase display path (e.g. W01.P02.S06 or P02)",
        ),
    ] = None,
    feature: Annotated[
        str | None,
        typer.Option(
            "--feature",
            help="Feature tag (kebab-case; leading '#' optional)",
        ),
    ] = None,
) -> None:
    """Print a well-formed commit-linkage trailer line.

    Exactly one of ``--step`` or ``--feature`` is required. The emitted line
    is suitable for scripting into a commit template or appending to a commit
    message. Invalid input is a usage error (exit 1); emission never produces
    a malformed trailer.
    """
    from vaultspec_core.plan.commands._errors import PlanCommandError
    from vaultspec_core.plan.trailer import (
        format_feature_trailer,
        format_step_trailer,
    )

    if (step is None) == (feature is None):
        raise PlanCommandError("provide exactly one of --step or --feature.")

    try:
        if step is not None:
            typer.echo(format_step_trailer(step))
        else:
            assert feature is not None
            typer.echo(format_feature_trailer(feature))
    except ValueError as exc:
        raise PlanCommandError(str(exc)) from exc


@trailer_app.command("validate")
def cmd_trailer_validate(
    message_file: Annotated[
        Path,
        typer.Argument(
            help="Path to a commit-message file (e.g. .git/COMMIT_EDITMSG)",
        ),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit findings as JSON")
    ] = False,
) -> None:
    """Validate the commit-linkage trailers in a commit-message file.

    Reports any malformed ``Vaultspec-Step`` / ``Vaultspec-Feature`` trailer
    and **always exits zero**, so it is safe to wire as an advisory
    ``commit-msg`` hook: a malformed or absent trailer never blocks a commit
    (the convention is enrichment, never a prerequisite). An unreadable
    message file is likewise reported and tolerated.
    """
    from vaultspec_core.plan.trailer import validate_message

    try:
        message = message_file.read_text(encoding="utf-8")
    except OSError as exc:
        if json_output:
            from vaultspec_core.cli.rendering import json_envelope

            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.plan.trailer.validate",
                        "unchanged",
                        {"unreadable": str(message_file), "problems": []},
                    ),
                    indent=2,
                )
            )
        else:
            typer.echo(f"trailer: could not read {message_file}: {exc}", err=True)
        return

    problems = validate_message(message)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        payload = {
            "problems": [
                {
                    "key": p.key,
                    "value": p.value,
                    "line": p.line_number,
                    "reason": p.reason,
                }
                for p in problems
            ]
        }
        typer.echo(
            json.dumps(
                json_envelope("vault.plan.trailer.validate", "unchanged", payload),
                indent=2,
            )
        )
        return

    if not problems:
        return
    for problem in problems:
        typer.echo(
            f"trailer (advisory) line {problem.line_number}: "
            f"{problem.key}: {problem.value!r} - {problem.reason}",
            err=True,
        )
