"""``vaultspec-core vault adr crossref``: the decisions an ADR should link.

The verb presents :mod:`vaultspec_core.crossref` and adds no judgment of its
own. Which ADRs are judged, the bounds, the verdicts, the writes and the next
step after an outcome that did not judge all come from the crossref package,
so this verb and the MCP ``crossref`` tool give the same answer. The ``--json``
envelope's ``data`` is the package's one projection of the outcome. This module
owns only the terminal rendering and the envelope around the data.

One named ADR is judged on its own. Several named ADRs, a ``--feature``, or
``--all`` make a sweep: sources in stem order, at most ``--max-sources`` of
them, resumable with ``--after`` from the ``next_after`` a previous sweep
reported.

Exit codes:

``0``
    Every source taken was judged (envelope ``unchanged``, or ``updated`` when
    ``--apply`` wrote links), or hosted search is not configured (envelope
    ``skipped``); the reply names the manual path instead.
``1``
    Hosted search is configured but a source could not be judged (envelope
    ``failed``); a sweep stops there and reports where to resume.
``2``
    The input is invalid: no source, a source that is not an ADR of this
    vault, a vault larger than one run reads, or an option out of range.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._errors import handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.cli.vault_cmd_app import FeatureFilterOption, adr_app
from vaultspec_core.crossref import (
    DEFAULT_SOURCES,
    MAX_SOURCES,
    CorpusTooLargeError,
    CrossrefStatus,
    InvalidSourceError,
    VerdictKind,
    outcome_fields,
    remediation,
    sweep_fields,
)

if TYPE_CHECKING:
    from vaultspec_core.cli.rendering import Outcome, TreeLine
    from vaultspec_core.crossref import CrossrefOutcome, SweepOutcome

__all__ = ["cmd_adr_crossref"]


def _envelope_status(outcomes: tuple[CrossrefOutcome, ...]) -> Outcome:
    from vaultspec_core.cli.rendering import Outcome

    if any(o.status is CrossrefStatus.UNAVAILABLE for o in outcomes):
        return Outcome.FAILED
    if any(o.status is CrossrefStatus.NOT_CONFIGURED for o in outcomes):
        return Outcome.SKIPPED
    if any(o.written for o in outcomes):
        return Outcome.UPDATED
    return Outcome.UNCHANGED


def _source_lines(outcome: CrossrefOutcome) -> list[TreeLine]:
    """Render one source: its status line, then each verdict."""
    from vaultspec_core.cli.rendering import OUTCOME_STYLE, TreeLine

    if outcome.status is not CrossrefStatus.OK:
        glyph, style = OUTCOME_STYLE[_envelope_status((outcome,))]
        label = f"{outcome.source}: {outcome.status.value.replace('_', ' ')}"
        if outcome.reason is not None:
            label += f" ({outcome.reason.value})"
        lines = [TreeLine(label, glyph=glyph, style=style)]
        note = remediation(outcome)
        if note is not None:
            lines.append(TreeLine(note, depth=1))
        return lines
    count = len(outcome.links)
    head = f"{outcome.source}: {count} link{'' if count == 1 else 's'}"
    lines = [TreeLine(head, style="bold")]
    for verdict in outcome.verdicts:
        mark = "declared" if verdict.declared else "new"
        if verdict.applied:
            mark = "written"
        style = "green" if verdict.kind is VerdictKind.LINK else "yellow"
        text = (
            f"{verdict.kind.value} {verdict.score:.2f} {verdict.relation} "
            f"{verdict.stem} ({mark})"
        )
        lines.append(TreeLine(text, depth=1, style=style))
    if outcome.bounds is not None and outcome.bounds.unjudged_declared:
        extra = len(outcome.bounds.unjudged_declared)
        lines.append(
            TreeLine(f"{extra} declared link(s) not judged", depth=1, style="dim")
        )
    return lines


def _sweep_lines(sweep: SweepOutcome) -> list[TreeLine]:
    from vaultspec_core.cli.rendering import TreeLine

    lines: list[TreeLine] = []
    for outcome in sweep.outcomes:
        lines += _source_lines(outcome)
    if sweep.stopped is not None:
        lines.append(TreeLine(f"stopped early: {sweep.stopped}", style="yellow"))
    if sweep.remaining:
        resume = f"; resume with --after {sweep.next_after}" if sweep.next_after else ""
        lines.append(
            TreeLine(f"{sweep.remaining} source(s) remaining{resume}", style="dim")
        )
    return lines


def _emit(
    data: dict[str, object],
    outcomes: tuple[CrossrefOutcome, ...],
    lines: list[TreeLine],
    *,
    json_output: bool,
) -> None:
    import json

    from vaultspec_core.cli.rendering import Outcome, json_envelope, render_tree

    status = _envelope_status(outcomes)
    if json_output:
        envelope = json_envelope("vault.adr.crossref", status, data)
        typer.echo(json.dumps(envelope, **json_format_kwargs(), default=str))
    else:
        render_tree(lines, title="ADR cross-references")
    raise typer.Exit(1 if status is Outcome.FAILED else 0)


@adr_app.command("crossref")
def cmd_adr_crossref(
    refs: Annotated[
        list[str] | None,
        typer.Argument(
            help="ADRs to cross-reference: stem, filename, path or [[wiki-link]]"
        ),
    ] = None,
    feature: FeatureFilterOption = None,
    all_adrs: Annotated[
        bool, typer.Option("--all", help="Sweep every ADR that still governs")
    ] = False,
    isolated: Annotated[
        bool,
        typer.Option("--isolated", help="Sweep only ADRs that link no other ADR"),
    ] = False,
    after: Annotated[
        str | None,
        typer.Option("--after", help="Resume a sweep after this ADR stem"),
    ] = None,
    max_sources: Annotated[
        int,
        typer.Option(
            "--max-sources",
            min=1,
            max=MAX_SOURCES,
            help="Most ADRs one sweep judges",
        ),
    ] = DEFAULT_SOURCES,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write each new link verdict into related:"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Find the ADRs a decision should cross-reference, within fixed bounds.

    Judges each source ADR against every other ADR with hosted search: a
    code-only rank, one bounded Choice stage and a bounded pair judgment. Lists
    the candidates judged to be links and the declared links judged weak. With
    --apply, writes the new links into the source's related: field. Without a
    hosted-search key it sends nothing and names the manual path instead.
    """
    apply_target(target, json_output=json_output)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.crossref import crossref_adr, crossref_sweep

    names = list(refs or [])
    if not names and feature is None and not all_adrs and not isolated:
        raise typer.BadParameter(
            "name an ADR, or sweep with --feature, --isolated or --all",
            param_hint="'REFS'",
        )
    root = _get_ctx().target_dir
    single = len(names) == 1 and feature is None and not all_adrs and not isolated
    try:
        if single and after is None:
            outcome = crossref_adr(root, names[0], apply=apply)
            _emit(
                outcome_fields(outcome),
                (outcome,),
                _source_lines(outcome),
                json_output=json_output,
            )
            return
        sweep = crossref_sweep(
            root,
            names,
            feature=feature,
            isolated=isolated,
            after=after,
            max_sources=max_sources,
            apply=apply,
        )
    except (InvalidSourceError, CorpusTooLargeError) as exc:
        raise typer.BadParameter(str(exc), param_hint="'REFS'") from exc
    except OSError as exc:
        handle_error(exc, json_output=json_output)
        return
    _emit(
        sweep_fields(sweep),
        sweep.outcomes,
        _sweep_lines(sweep),
        json_output=json_output,
    )
