"""``vaultspec-core vault search``: ask the vault a question, read the passage.

The verb presents hosted vault search and adds no search logic of its own. The
filters, the page ceiling, the three outcomes and the next step after an outcome
that did not rank all come from :mod:`vaultspec_core.search`, so this verb and
the MCP ``search`` tool give the same answer to the same question. This module
owns only the shape of that answer: on a terminal and in the ``--json``
envelope.

Both shapes carry the window the search applied (``returned``, ``total``,
``truncated``) and the excerpts exactly as the search package bounded them,
each marked when it was cut; nothing is clipped here. The terminal verdict
says nothing in the vault answers only when the search read every record. The
key never reaches this module; the search package reports only whether one is
configured.

Exit codes:

``0``
    The search ran, whether or not anything answers (envelope ``unchanged``),
    or hosted search is not configured (envelope ``skipped``). Not configured is
    the default state of a workspace without a key, and the reply names the
    search to run instead, so it is guidance rather than failure.
``1``
    Hosted search is configured but did not finish (envelope ``failed``), or
    the workspace or the vault cannot be read.
``2``
    The input is invalid: a blank or overlong query, a record type search does
    not rank, or a limit outside ``1..MAX_RESULTS``. These are refused before
    anything is read or sent, as every malformed option is.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Annotated, Final

import typer

from vaultspec_core.cli._errors import handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.cli.vault_cmd_app import (
    DateFilterOption,
    FeatureFilterOption,
    vault_app,
)
from vaultspec_core.core.windowing import elision_line
from vaultspec_core.search import (
    DEFAULT_RESULTS,
    MAX_RESULTS,
    PREMISE_CONFLICT_THRESHOLD,
    SEARCHABLE_TYPES,
    InvalidQueryError,
    SearchStatus,
    remediation,
)

if TYPE_CHECKING:
    from vaultspec_core.cli.rendering import Outcome, TreeLine
    from vaultspec_core.search import Excerpt, SearchHit, SearchOutcome
    from vaultspec_core.vaultcore.models import DocType

__all__ = ["cmd_search"]

#: The record types ``--type`` accepts, in the order help and errors list them.
_TYPE_NAMES: Final = ", ".join(sorted(doc_type.value for doc_type in SEARCHABLE_TYPES))


def _envelope_status(status: SearchStatus) -> Outcome:
    """Return the envelope word for a search outcome.

    Only a configured search that did not finish is a failure; a missing key
    is a precondition that skipped the search.
    """
    from vaultspec_core.cli.rendering import Outcome

    if status is SearchStatus.UNAVAILABLE:
        return Outcome.FAILED
    if status is SearchStatus.NOT_CONFIGURED:
        return Outcome.SKIPPED
    return Outcome.UNCHANGED


def _record_types(values: list[str] | None) -> frozenset[DocType] | None:
    """Resolve the ``--type`` values to the record types search ranks.

    Args:
        values: The raw option values, or ``None`` when none were given.

    Returns:
        The selected record types, or ``None`` to search every searchable type.

    Raises:
        typer.BadParameter: If a value names no searchable record type.
    """
    if not values:
        return None
    searchable = {doc_type.value: doc_type for doc_type in SEARCHABLE_TYPES}
    unknown = [value for value in values if value not in searchable]
    if unknown:
        raise typer.BadParameter(
            f"not a searchable record type: {', '.join(unknown)} "
            f"(choose from {_TYPE_NAMES})",
            param_hint="'--type'",
        )
    return frozenset(searchable[value] for value in values)


def _hit_payload(hit: SearchHit) -> dict[str, object]:
    """Render one hit for the JSON envelope.

    ``name`` is dropped because it is the stem of ``path``, and an excerpt the
    search did not choose is absent rather than ``null``.
    """
    row = dataclasses.asdict(hit)
    del row["name"]
    for key in ("excerpt", "supporting"):
        if row[key] is None:
            del row[key]
    return row


def _outcome_payload(outcome: SearchOutcome) -> dict[str, object]:
    """Render an outcome as the envelope's ``data``.

    The query is not echoed back: the caller supplied it. Keys that do not
    apply to the outcome are absent rather than ``null``.
    """
    payload: dict[str, object] = {"status": outcome.status.value}
    if outcome.status is SearchStatus.OK:
        payload["answered"] = outcome.answered
        payload["hits"] = [_hit_payload(hit) for hit in outcome.hits]
    if outcome.window is not None:
        payload.update(outcome.window.as_fields())
    if outcome.reason is not None:
        payload["reason"] = outcome.reason.value
    note = remediation(outcome)
    if note is not None:
        payload["remediation"] = note
    if outcome.usage is not None:
        payload["usage"] = dataclasses.asdict(outcome.usage)
    return payload


def _json_text(outcome: SearchOutcome) -> str:
    """Render *outcome* as the ``--json`` envelope text the command prints."""
    import json

    from vaultspec_core.cli.rendering import json_envelope

    status = _envelope_status(outcome.status)
    envelope = json_envelope("vault.search", status, _outcome_payload(outcome))
    # The excerpt caps bound UTF-8 bytes. ASCII escaping would carry each CJK
    # character in six bytes and each emoji in twelve, so the reply budget the
    # caps guarantee holds only when the text travels as the UTF-8 it is.
    return json.dumps(envelope, **json_format_kwargs(), default=str)


def _passage_lines(excerpt: Excerpt, *, depth: int) -> list[TreeLine]:
    """Render an excerpt's text as indented lines, marked when it was cut."""
    from vaultspec_core.cli.rendering import TRUNCATE_MARKER, TreeLine

    lines = [TreeLine(line, depth=depth) for line in excerpt.text.splitlines()]
    if excerpt.truncated:
        lines.append(TreeLine(TRUNCATE_MARKER, depth=depth, style="dim"))
    return lines


def _hit_lines(rank: int, hit: SearchHit) -> list[TreeLine]:
    """Render one ranked hit: its header, any premise note, and its excerpts.

    The header reads rank, record name, type, then ``path:start-end`` and the
    section; the section is last because it is the one field that may contain
    spaces.
    """
    from vaultspec_core.cli.rendering import TreeLine

    fields = [str(rank), hit.name, hit.doc_type, hit.path]
    if hit.excerpt is not None:
        fields[-1] += f":{hit.excerpt.line_start}-{hit.excerpt.line_end}"
        fields.append(hit.excerpt.section)
    lines = [TreeLine(" ".join(field for field in fields if field), style="bold")]
    if hit.premise_conflict >= PREMISE_CONFLICT_THRESHOLD:
        lines.append(
            TreeLine(
                "may contradict an assumption in your question "
                f"({hit.premise_conflict:.2f})",
                depth=1,
                glyph="!",
                style="yellow",
            )
        )
    if hit.excerpt is None:
        lines.append(TreeLine("no answering passage located", depth=1, style="dim"))
    else:
        lines += _passage_lines(hit.excerpt, depth=1)
    if hit.supporting is not None:
        extra = hit.supporting
        also = f"also {hit.path}:{extra.line_start}-{extra.line_end} {extra.section}"
        lines.append(TreeLine(also.rstrip(), depth=1, style="dim"))
        lines += _passage_lines(extra, depth=2)
    return lines


def _verdict_line(outcome: SearchOutcome) -> TreeLine:
    """Render the verdict of a ranked outcome.

    "Nothing answers" is claimed only when every record was read; with records
    unscored, the verdict covers the records that were.
    """
    from vaultspec_core.cli.rendering import TreeLine

    if outcome.answered:
        return TreeLine("answered", style="green")
    if outcome.abstained:
        return TreeLine("nothing in the vault answers this", style="yellow")
    return TreeLine("no record that was read answers this", style="yellow")


def _outcome_lines(outcome: SearchOutcome) -> list[TreeLine]:
    """Render an outcome for the terminal: the verdict first, then the hits."""
    from vaultspec_core.cli.rendering import OUTCOME_STYLE, TreeLine, summary_line

    if outcome.status is not SearchStatus.OK:
        glyph, style = OUTCOME_STYLE[_envelope_status(outcome.status)]
        label = outcome.status.value.replace("_", " ")
        if outcome.reason is not None:
            label += f" ({outcome.reason.value})"
        lines = [TreeLine(label, glyph=glyph, style=style)]
        note = remediation(outcome)
        if note is not None:
            lines.append(TreeLine(note, depth=1))
        return lines

    lines = [_verdict_line(outcome)]
    if outcome.unscored:
        noun = "record" if outcome.unscored == 1 else "records"
        lines.append(
            TreeLine(
                f"{outcome.unscored} {noun} the provider would not read in full",
                style="yellow",
            )
        )
    for rank, hit in enumerate(outcome.hits, start=1):
        lines += _hit_lines(rank, hit)
    if outcome.window is not None:
        noun = "hit" if outcome.window.returned == 1 else "hits"
        lines.append(TreeLine(summary_line(outcome.window.returned, noun), style="dim"))
        notice = elision_line(outcome.window, "hits")
        if notice is not None:
            lines.append(TreeLine(notice, style="dim"))
    return lines


@vault_app.command("search")
def cmd_search(
    query: Annotated[
        str, typer.Argument(help="The question to ask the vault, in plain language")
    ],
    record_types: Annotated[
        list[str] | None,
        typer.Option(
            "--type",
            help=f"Search only this record type ({_TYPE_NAMES}); repeatable",
        ),
    ] = None,
    feature: FeatureFilterOption = None,
    date: DateFilterOption = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit", min=1, max=MAX_RESULTS, help="Maximum ranked records to return"
        ),
    ] = DEFAULT_RESULTS,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Ask the vault a question and read the passages that answer it.

    Ranks the vault's records against QUERY with hosted search and quotes the
    answering passage of each, with its line range. Says so when nothing in the
    vault answers. Without a hosted-search key it runs nothing and names the
    search to use instead.
    """
    types = _record_types(record_types)
    apply_target(target, json_output=json_output)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.search import search_vault

    try:
        outcome = search_vault(
            _get_ctx().target_dir,
            query,
            doc_types=types,
            feature=feature,
            date=date,
            limit=limit,
        )
    except InvalidQueryError as exc:
        raise typer.BadParameter(str(exc), param_hint="'QUERY'") from exc
    except OSError as exc:
        handle_error(exc, json_output=json_output)
        return

    from vaultspec_core.cli.rendering import Outcome, render_tree

    if json_output:
        typer.echo(_json_text(outcome))
    else:
        render_tree(_outcome_lines(outcome), title="Vault search")
    failed = _envelope_status(outcome.status) is Outcome.FAILED
    raise typer.Exit(1 if failed else 0)
