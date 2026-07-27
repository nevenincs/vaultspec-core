"""CLI wiring for explicit, manifest-driven vault document archival.

The command owns manifest decoding and presentation only.  Validation and
every filesystem mutation belong to :mod:`vaultspec_core.vaultcore.batch_archive`.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 - Typer inspects this command annotation.
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

__all__ = ["archive_app"]


archive_app = make_app(
    help="Archive explicitly listed vault documents.",
    no_args_is_help=True,
)


def _manifest_entries(manifest: Path) -> list[str]:
    """Read UTF-8 manifest entries without interpreting their paths.

    The core archive owner validates every entry against the resolved target.
    Keeping this boundary narrow prevents the CLI from gaining a second path
    policy or a filesystem-mutation path.
    """
    return manifest.read_text(encoding="utf-8").splitlines()


@archive_app.command("documents")
def cmd_archive_documents(
    manifest: Annotated[
        Path,
        typer.Option(
            "--manifest",
            help="UTF-8 newline-separated repository-relative .vault/*.md paths",
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview the archive without writing"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Archive exactly the documents named in a UTF-8 manifest."""
    apply_target(target, json_output=json_output)
    from vaultspec_core.core.types import get_context
    from vaultspec_core.vaultcore.batch_archive import (
        ArchiveDocumentsError,
        archive_documents,
    )

    root_dir = get_context().target_dir
    try:
        result = archive_documents(
            root_dir,
            _manifest_entries(manifest),
            dry_run=dry_run,
        )
    except (ArchiveDocumentsError, OSError) as exc:
        handle_error(exc, json_output=json_output)
        return

    if result.status == "updated" and not dry_run:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    payload = result.to_dict()
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope("vault.archive.documents", result.status, payload),
                indent=2,
            )
        )
        return

    from vaultspec_core.console import get_console

    console = get_console()
    paths = payload["paths"]
    assert isinstance(paths, list)
    if dry_run:
        console.print(
            "[yellow]Dry-run:[/yellow] would archive "
            f"{result.archived_count} documents."
        )
    else:
        console.print(f"[green]Archived {result.archived_count} documents.[/green]")
    for path in paths:
        console.print(f"  {path}")
