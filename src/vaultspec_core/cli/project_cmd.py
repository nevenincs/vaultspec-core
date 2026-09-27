"""Cold project coordination verbs, also exposed through the CLI gateway."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._target import TargetOption, resolve_effective_target
from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.cli.rendering import TreeLine, json_envelope, render_tree
from vaultspec_core.project import project_context

project_app = make_app(
    help="Collect bounded context for multi-workstream coordination."
)


@project_app.command("context")
def cmd_context(
    objective: Annotated[str, typer.Argument(help="Developer outcome to prioritize.")],
    repo: Annotated[
        str | None, typer.Option(help="Optional github.com OWNER/REPO to read.")
    ] = None,
    previous: Annotated[
        Path | None,
        typer.Option(
            help="Previous JSON result; reuse unchanged judgments for up to one hour.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    limit: Annotated[
        int, typer.Option(min=1, max=10, help="Maximum attention items to return.")
    ] = 5,
    no_hosted: Annotated[
        bool,
        typer.Option(
            "--no-hosted", help="Disable hosted ranking even when a key is configured."
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON.")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Read local work and optional GitHub state; propose a bounded attention order.

    No tracker or repository writes. No key is required. Source failures and hosted
    failures preserve available observations and report incomplete coverage.
    """
    try:
        result = project_context(
            resolve_effective_target(target),
            objective,
            repo=repo,
            limit=limit,
            previous=Path(previous).resolve() if previous is not None else None,
            hosted=not no_hosted,
        )
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from error
    if json_output:
        typer.echo(
            json.dumps(
                json_envelope("project.context", "unchanged", result),
                **json_format_kwargs(),
            )
        )
        return
    _render(result)


def _render(result: dict[str, object]) -> None:
    items = cast("list[dict[str, object]]", result["items"])
    sources = cast("list[dict[str, object]]", result["sources"])
    hosted = cast("dict[str, object]", result["hosted"])
    lines = [TreeLine(str(result["ordering"]))]
    for index, item in enumerate(items, 1):
        lines.append(TreeLine(f"{index}. {item['kind']}: {item['title']}"))
        lines.append(TreeLine(str(item["id"]), depth=1))
        signals = cast("list[str]", item["signals"])
        if signals:
            lines.append(TreeLine(", ".join(signals), depth=1))
        facts = cast("dict[str, object]", item["facts"])
        if facts.get("status_error"):
            lines.append(
                TreeLine(
                    f"Working-tree status unavailable: {facts['status_error']}", depth=1
                )
            )
        lines.append(TreeLine(str(item["next_action"]), depth=1))
    lines.append(
        TreeLine(
            f"Showing {result['returned']} of {result['observed_items']} items; "
            f"{result['shortlisted']} shortlisted."
        )
    )
    for source in sources:
        lines.append(
            TreeLine(
                f"{source['name']}: {source['status']} ({source['count']} items"
                f"{', window truncated' if source['truncated'] else ''})"
                f"{'; ' + str(source['reason']) if source['reason'] else ''}"
            )
        )
    lines.append(
        TreeLine("Uncollected: " + ", ".join(cast("list[str]", result["uncollected"])))
    )
    lines.append(
        TreeLine(
            f"Hosted: {hosted['status']}; {hosted['requests']} requests, "
            f"{hosted['cache_hits']} reused; observed through {result['observed_to']}"
        )
    )
    render_tree(lines, title=f"Project attention: {result['objective']}")


__all__ = ["project_app"]
