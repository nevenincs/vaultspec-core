"""``vaultspec-core spec reference`` - regenerate the bundled CLI reference.

Defines :data:`reference_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd`
onto :data:`~vaultspec_core.cli.spec_cmd_app.spec_app` as the ``reference``
command group.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli.spec_cmd_shared import emit_json

reference_app = make_app(
    help="Generate the derivable regions of the bundled CLI reference",
    no_args_is_help=True,
)


@reference_app.command("generate")
def cmd_reference_generate(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Render in memory and diff against the committed reference; "
                "exit non-zero on mismatch without writing."
            ),
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Regenerate the generator-owned regions of the bundled CLI reference.

    The bundled machine-facing reference at
    ``src/vaultspec_core/builtins/reference/cli.md`` carries generator-owned
    zones (delimited by ``vaultspec:generated`` HTML-comment markers) and
    hand-written prose zones. This verb rewrites only the managed zones from
    the live Typer command tree, leaving the prose untouched.

    Default (write) mode rewrites the file in place when the managed regions
    have drifted. ``--check`` mode renders into memory, diffs against the
    committed file, prints the diff, and exits non-zero on mismatch (the CI and
    pre-commit entry point); it exits 0 when the reference is already in sync.
    """
    from vaultspec_core.cli.reference_gen import (
        ReferenceMarkerError,
        generate_all,
    )

    try:
        results = generate_all(check=check)
    except (ReferenceMarkerError, OSError) as exc:
        if json_output:
            emit_json("spec.reference.generate", "failed", {"message": str(exc)})
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    files = [
        {
            "path": str(result.path),
            "name": result.path.name,
            "in_sync": result.in_sync,
            "changed": result.changed,
            "diff": result.diff,
        }
        for result in results
    ]
    out_of_sync = [result for result in results if result.changed]

    if check:
        if not out_of_sync:
            if json_output:
                emit_json(
                    "spec.reference.generate",
                    "unchanged",
                    {"files": files, "in_sync": True},
                )
            else:
                names = ", ".join(result.path.name for result in results)
                typer.echo(f"Generated references in sync: {names}.")
            raise typer.Exit(0)
        if json_output:
            emit_json(
                "spec.reference.generate",
                "failed",
                {"files": files, "in_sync": False},
            )
        else:
            for result in out_of_sync:
                typer.echo(
                    f"Generated reference {result.path.name} is out of sync with "
                    "the live CLI surface.",
                    err=True,
                )
                typer.echo(result.diff, err=True)
            typer.echo(
                "  Run 'vaultspec-core spec reference generate' to refresh it.",
                err=True,
            )
        raise typer.Exit(code=1)

    if not out_of_sync:
        if json_output:
            emit_json(
                "spec.reference.generate",
                "unchanged",
                {"files": files, "in_sync": True},
            )
        else:
            names = ", ".join(result.path.name for result in results)
            typer.echo(f"Generated references already up to date: {names}.")
        raise typer.Exit(0)

    if json_output:
        emit_json(
            "spec.reference.generate",
            "updated",
            {"files": files},
        )
    else:
        names = ", ".join(result.path.name for result in out_of_sync)
        typer.echo(f"Regenerated managed regions of: {names}.")
    raise typer.Exit(0)
