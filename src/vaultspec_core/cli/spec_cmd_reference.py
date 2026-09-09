"""``vaultspec-core spec reference`` - regenerate the bundled references.

Defines :data:`reference_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd`
onto :data:`~vaultspec_core.cli.spec_cmd_app.spec_app` as the ``reference``
command group. ``generate`` owns the managed regions of the reference
documents; ``snapshot`` owns the published-surface record those regions
attribute against.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli.spec_cmd_shared import emit_json

if TYPE_CHECKING:
    from vaultspec_core.cli.reference_surface import Surface

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


@reference_app.command("snapshot")
def cmd_reference_snapshot(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Report whether the snapshot is due a refresh; exit non-zero "
                "when it is, without writing."
            ),
        ),
    ] = False,
    emit: Annotated[
        bool,
        typer.Option(
            "--emit",
            help=(
                "Print this build's own surface as a snapshot document to "
                "stdout and write nothing."
            ),
        ),
    ] = False,
    verify: Annotated[
        typer.FileText | None,
        typer.Option(
            "--verify",
            help=(
                "Compare a surface document (from --emit) against the "
                "committed snapshot; exit non-zero when they differ."
            ),
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Record the published command and MCP tool surface.

    The snapshot at ``src/vaultspec_core/builtins/reference/published-surface.json``
    is what the generated references attribute against: the difference between
    it and the live surface is what they render as unreleased, in place of
    hand-written per-command caveats.

    Default (write) mode refreshes the snapshot from the live surface, but only
    when the tree declares a different version from the one recorded. That
    restriction is the contract: the recorded surface belongs to a release, so
    the release candidate branch - where the version is already the candidate's
    and the tree is the one about to be tagged - is the only place it may be
    rewritten. On main between releases the versions match and this is a no-op,
    because rewriting there would restamp unreleased commands as published.

    ``--check`` reports that state without writing, for CI. ``--emit`` prints
    this build's own surface, which is how a published distribution is read
    back inside an isolated install. ``--verify`` compares such a document
    against the committed snapshot, which is how the publish lane proves a
    released artifact matches the reference shipped for it.
    """
    from vaultspec_core.cli.reference_surface import (
        SurfaceSnapshotError,
        capture_surface,
        deserialize_surface,
        load_published_surface,
        published_surface_path,
        refresh_reason,
        serialize_surface,
        write_published_surface,
    )

    if emit:
        typer.echo(serialize_surface(capture_surface()), nl=False)
        raise typer.Exit(0)

    try:
        published = load_published_surface()
    except SurfaceSnapshotError as exc:
        if json_output:
            emit_json("spec.reference.snapshot", "failed", {"message": str(exc)})
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if verify is not None:
        try:
            candidate = deserialize_surface(verify.read())
        except SurfaceSnapshotError as exc:
            if json_output:
                emit_json("spec.reference.snapshot", "failed", {"message": str(exc)})
            else:
                typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _report_verification(candidate, published, json_output=json_output)
        return

    live = capture_surface()
    reason = refresh_reason(live, published)
    path = published_surface_path()

    if reason is None:
        payload = {
            "path": str(path),
            "version": published.version,
            "refreshed": False,
        }
        if json_output:
            emit_json("spec.reference.snapshot", "unchanged", payload)
        else:
            typer.echo(
                f"Published-surface snapshot holds {published.version}; "
                "the tree declares the same version, so it is not refreshed."
            )
        raise typer.Exit(0)

    if check:
        payload = {"path": str(path), "reason": reason, "refreshed": False}
        if json_output:
            emit_json("spec.reference.snapshot", "failed", payload)
        else:
            typer.echo(f"Published-surface snapshot is stale: {reason}.", err=True)
            typer.echo(
                "  Run 'vaultspec-core spec reference snapshot' to refresh it.",
                err=True,
            )
        raise typer.Exit(code=1)

    changed = write_published_surface(live)
    payload = {
        "path": str(path),
        "version": live.version,
        "refreshed": changed,
        "reason": reason,
    }
    if json_output:
        emit_json(
            "spec.reference.snapshot", "updated" if changed else "unchanged", payload
        )
    else:
        typer.echo(
            f"Published-surface snapshot refreshed to {live.version} "
            f"({len(live.commands)} commands, {len(live.mcp_tools)} MCP tools)."
        )
    raise typer.Exit(0)


def _report_verification(
    candidate: Surface, published: Surface, *, json_output: bool
) -> None:
    """Emit the outcome of a ``--verify`` comparison and exit accordingly."""
    from vaultspec_core.cli.reference_surface import unreleased_surface

    missing = unreleased_surface(published, candidate)
    extra = unreleased_surface(candidate, published)
    version_matches = candidate.version == published.version

    if version_matches and missing.is_empty() and extra.is_empty():
        payload = {"version": candidate.version, "matches": True}
        if json_output:
            emit_json("spec.reference.snapshot", "unchanged", payload)
        else:
            typer.echo(
                f"Distribution surface matches the committed snapshot for "
                f"{candidate.version}."
            )
        raise typer.Exit(0)

    payload = {
        "matches": False,
        "distribution_version": candidate.version,
        "snapshot_version": published.version,
        "absent_from_distribution": {
            "commands": list(missing.commands),
            "flags": {name: list(f) for name, f in missing.flags.items()},
            "mcp_tools": list(missing.mcp_tools),
        },
        "absent_from_snapshot": {
            "commands": list(extra.commands),
            "flags": {name: list(f) for name, f in extra.flags.items()},
            "mcp_tools": list(extra.mcp_tools),
        },
    }
    if json_output:
        emit_json("spec.reference.snapshot", "failed", payload)
    else:
        if not version_matches:
            typer.echo(
                f"Distribution declares {candidate.version}; the snapshot "
                f"records {published.version}.",
                err=True,
            )
        for label, diff in (
            ("documented but absent from the distribution", missing),
            ("present in the distribution but undocumented", extra),
        ):
            if diff.is_empty():
                continue
            typer.echo(f"  {label}:", err=True)
            for name in diff.commands:
                typer.echo(f"    command  {name}", err=True)
            for name, flags in diff.flags.items():
                typer.echo(f"    flags    {name} {' '.join(flags)}", err=True)
            for name in diff.mcp_tools:
                typer.echo(f"    mcp tool {name}", err=True)
    raise typer.Exit(code=1)
