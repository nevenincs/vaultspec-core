"""``vaultspec-core doctor`` and ``vaultspec-core check-providers``.

Defines :func:`cmd_doctor` and :func:`cmd_check_providers`, mounted by
:mod:`vaultspec_core.cli.root` as top-level commands on
:data:`~vaultspec_core.cli.root_app.app`.
"""

from __future__ import annotations

from typing import Annotated

import typer

from vaultspec_core.cli._target import (
    TargetOption,
    apply_target,
    resolve_effective_target,
)


def cmd_check_providers() -> None:
    """Guard against committing provider artifacts.

    Inspects the git staging area for files that should never be
    committed (provider directories, generated configs, manifests).
    Used as a pre-commit hook entry point.
    """
    from vaultspec_core.core.commands import check_staged_provider_artifacts

    violations = check_staged_provider_artifacts()
    if violations:
        typer.echo(
            "Error: provider artifacts must not be committed:",
            err=True,
        )
        for v in violations:
            typer.echo(f"  {v}", err=True)
        typer.echo(
            "\nRun 'git reset HEAD <file>' to unstage, "
            "or 'git rm --cached <file>' to untrack.",
            err=True,
        )
        raise typer.Exit(code=1)


def cmd_doctor(
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Diagnose overall workspace and vault health.

    Runs both spec workspace diagnosis and vault check-all under a unified exit code.

    Exit codes: 0 = all ok, 1 = warnings, 2 = errors.
    """
    import contextlib
    import dataclasses
    import json
    import logging

    import typer

    from vaultspec_core.cli.rendering import json_envelope
    from vaultspec_core.cli.spec_cmd import doctor_exit_code, render_diagnosis_table
    from vaultspec_core.console import get_console
    from vaultspec_core.core.diagnosis import diagnose
    from vaultspec_core.vaultcore.checks import render_check_result, run_all_checks

    effective_dir = resolve_effective_target(target)

    if not effective_dir.exists():
        typer.echo(f"Error: target directory does not exist: {effective_dir}", err=True)
        raise typer.Exit(code=2)

    previous_logging_disable = logging.root.manager.disable
    if json_output:
        logging.disable(logging.CRITICAL)

    try:
        with contextlib.suppress(Exception):
            apply_target(target)

        try:
            diag = diagnose(effective_dir, scope="full")
        except Exception as exc:
            typer.echo(f"Error: workspace diagnosis failed: {exc}", err=True)
            raise typer.Exit(code=2) from None

        try:
            results = run_all_checks(effective_dir)
        except Exception as exc:
            typer.echo(f"Error: vault checking failed: {exc}", err=True)
            raise typer.Exit(code=2) from None

    finally:
        if json_output:
            logging.disable(previous_logging_disable)

    spec_exit_code = doctor_exit_code(diag)
    vault_has_errors = any(r.error_count for r in results)
    vault_has_warnings = any(r.warning_count for r in results)

    if spec_exit_code == 2 or vault_has_errors:
        exit_code = 2
    elif spec_exit_code == 1 or vault_has_warnings:
        exit_code = 1
    else:
        exit_code = 0

    if json_output:
        data = {
            "spec": dataclasses.asdict(diag),
            "vault": {"checks": [dataclasses.asdict(r) for r in results]},
        }
        envelope = json_envelope(
            "doctor",
            "failed" if exit_code == 2 else "unchanged",
            data,
        )
        typer.echo(json.dumps(envelope, indent=2, default=str))
        raise typer.Exit(code=exit_code)

    console = get_console()
    render_diagnosis_table(console, diag)
    console.print()
    console.print("[bold]Vault Check - All[/bold]")
    for r in results:
        render_check_result(console, r, verbose=False)

    raise typer.Exit(code=exit_code)
