"""``vaultspec-core commit-gate``: the read-only check a commit hook runs.

Defines :func:`cmd_commit_gate`, mounted by :mod:`vaultspec_core.cli.root` as a
top-level command on :data:`~vaultspec_core.cli.root_app.app`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._target import (
    TargetOption,
    apply_target,
    resolve_effective_target,
)

if TYPE_CHECKING:
    from vaultspec_core.vaultcore.checks.staged import StagedGateOutcome


def _render(outcome: StagedGateOutcome, per_machine: list[str]) -> None:
    """Print what blocks and what is advisory, naming files and findings only.

    Deliberately prints no remediation command. Output from a commit hook is
    often acted on without review, and every repair verb this project has
    rewrites documents beyond the one a finding names.
    """
    blocking_ids = {id(diagnostic) for _name, diagnostic in outcome.blocking}
    advisory = [
        (result.check_name, diagnostic)
        for result in outcome.results
        for diagnostic in result.diagnostics
        if id(diagnostic) not in blocking_ids
    ]

    if outcome.blocking:
        typer.echo("Blocking - introduced by this commit:", err=True)
        for name, diagnostic in outcome.blocking:
            typer.echo(f"  {diagnostic.path}: [{name}] {diagnostic.message}", err=True)
    if per_machine:
        typer.echo(
            "Blocking - per-machine files are staged; unstage them with "
            "'git restore --staged <file>':",
            err=True,
        )
        for path in per_machine:
            typer.echo(f"  {path}", err=True)
    if advisory:
        typer.echo("Advisory - does not block:", err=True)
        for name, diagnostic in advisory:
            typer.echo(f"  {diagnostic.path}: [{name}] {diagnostic.message}", err=True)


def cmd_commit_gate(
    paths: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Files to check, relative to the workspace root. A commit hook "
                "passes the staged files; with none given, the staged files are "
                "read from git."
            ),
            show_default=False,
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Check the files a commit stages, in one read-only process.

    Checks each staged vault document with the checkers that judge a document
    on its own, and blocks only on errors the commit introduces: an error the
    document's committed version already carries is reported as advisory.
    Also blocks staged per-machine files (install manifest, snapshots, lock
    sentinels, local vault caches). Never writes, and never runs the
    whole-vault checks; run 'vaultspec-core vault check all' for those.

    Exit codes: 0 = nothing blocks, 1 = something blocks.
    """
    import contextlib
    import dataclasses

    from vaultspec_core.core.git_artifacts import per_machine_paths, staged_paths
    from vaultspec_core.vaultcore.checks.staged import gate_staged_documents

    root = resolve_effective_target(target)
    with contextlib.suppress(Exception):
        apply_target(target)

    candidates = list(paths) if paths else staged_paths(root)
    outcome = gate_staged_documents(root, candidates)
    per_machine = per_machine_paths(root, candidates)
    blocked = bool(outcome.blocking or per_machine)

    if json_output:
        from vaultspec_core.cli.spec_cmd_shared import emit_json

        emit_json(
            "commit-gate",
            "failed" if blocked else "unchanged",
            {
                "blocking": [
                    {"check": name, **dataclasses.asdict(diagnostic)}
                    for name, diagnostic in outcome.blocking
                ],
                "per_machine": per_machine,
                "results": [dataclasses.asdict(r) for r in outcome.results],
            },
        )
        raise typer.Exit(code=1 if blocked else 0)

    _render(outcome, per_machine)
    raise typer.Exit(code=1 if blocked else 0)
