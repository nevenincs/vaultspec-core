"""Cold review-context selection, also available through the MCP gateway."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._target import TargetOption, resolve_effective_target
from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.cli.rendering import json_envelope
from vaultspec_core.review import review_context

review_app = make_app(help="Select supporting context for a defined code review.")


@review_app.command("context")
def cmd_context(
    objective: Annotated[str, typer.Argument(help="Behavior or constraint to review.")],
    base: Annotated[str, typer.Option(help="Required base commit reference.")],
    candidate: Annotated[
        list[str],
        typer.Option(help="Tracked path[:start-end]; repeat for 1..12 passages."),
    ],
    head: Annotated[
        str | None,
        typer.Option(help="Target commit; omit for tracked working-tree changes."),
    ] = None,
    limit: Annotated[
        int, typer.Option(min=1, max=6, help="Maximum supporting passages to return.")
    ] = 3,
    previous: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Previous JSON result; reuse identical inputs for up to one hour.",
        ),
    ] = None,
    no_hosted: Annotated[
        bool,
        typer.Option(
            "--no-hosted", help="Disable hosted selection even with a configured key."
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON.")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Read a diff and explicit source locators; optionally rank supporting passages.

    A configured TypeSafe key opts in to sending the bounded diff, objective and
    candidate passages. Missing credentials or hosted failures preserve discovery
    order. This is not a review verdict or a test runner. No repository writes.
    """
    try:
        result = review_context(
            resolve_effective_target(target),
            objective,
            base=base,
            candidates=candidate,
            head=head,
            limit=limit,
            previous=Path(previous).resolve() if previous is not None else None,
            hosted=not no_hosted,
        )
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from error
    if json_output:
        typer.echo(
            json.dumps(
                json_envelope("review.context", "unchanged", result),
                **json_format_kwargs(),
            )
        )
        return
    hosted = cast("dict[str, object]", result["hosted"])
    typer.echo(f"Review context: {result['ordering']}; hosted {hosted['status']}")
    if hosted["reason"]:
        typer.echo(f"Fallback reason: {hosted['reason']}")
    scope = cast("dict[str, object]", result["scope"])
    typer.echo(f"Scope: {scope['base']} -> {scope['head'] or scope['source']}")
    if scope["diff_reason"]:
        typer.echo(f"Diff unavailable: {scope['diff_reason']}")
    for item in cast("list[dict[str, object]]", result["selected"]):
        typer.echo(f"\n{item['id']}: {item['locator']} ({item['sha256']})")
        typer.echo(str(item["content"]))
    for item in cast("list[dict[str, object]]", result["unselected"]):
        typer.echo(f"Unselected: {item['id']}: {item['locator']}")
    typer.echo(f"Excluded: {result['excluded']}")
    typer.echo(str(result["next_action"]))


__all__ = ["review_app"]
