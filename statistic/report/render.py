"""The report layer: the ``records.jsonl`` and ``report.md`` renderers.

Two artifacts land in the gitignored ``statistic/out/`` directory. The
``records.jsonl`` stream is the full normalized
:class:`~statistic.normalize.models.CallRecord` set, one JSON object per line,
written for re-analysis; the command itself survives only as its hash, since the
model never carried raw text, and the ``cwd``/``project`` path fields are passed
through :func:`redact_home` at serialization so a home-directory prefix collapses
to ``~`` while the project signal beneath it survives. The ``report.md`` document
renders the seven metric families for human reading and, by strict contract,
carries *only* aggregates, hashes, verb paths, tag values, counts, and costs -
never a raw command body, secret, or personal path.

The Markdown renderer is a pure function of the records and the inventory: it
reads no clock and touches no filesystem, so a fixed input yields a byte-stable
document that the report tests can assert exactly. Every path-shaped value that
leaves the layer - both the surfaced report fields and the serialized
``records.jsonl`` ``cwd``/``project`` - is passed through :func:`redact_home`,
which strips a home-directory prefix down to a ``~`` marker, so neither artifact
can leak a home path.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from statistic.metrics.cost import compute_cost
from statistic.metrics.feature_tags import compute_feature_tag_usage
from statistic.metrics.features import compute_features_utilized
from statistic.metrics.hotspots import compute_hotspots
from statistic.metrics.misses import compute_misses
from statistic.metrics.ngrams import compute_ngrams
from statistic.metrics.surface import compute_surface
from statistic.normalize.tokenize import EXECUTABLE

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from statistic.metrics.capability import CapabilityInventory
    from statistic.normalize.models import CallRecord

#: How many rows of each ranked table the report renders. Aggregates are large;
#: the report shows the head of each ranking, and the full stream lives in
#: ``records.jsonl`` for anyone who wants the tail.
_TOP_N = 25

#: Matches a home-directory prefix on either separator style so a surfaced path
#: collapses to a ``~`` marker before it can reach the report.
_HOME_PREFIX = re.compile(
    r"^(?:[A-Za-z]:)?[\\/]+(?:Users|home)[\\/]+[^\\/]+", re.IGNORECASE
)


def redact_home(path: str) -> str:
    """Collapse a home-directory prefix in *path* to a ``~`` marker.

    Args:
        path: A path-shaped string that might carry a home prefix.

    Returns:
        The path with any leading ``.../Users/<name>`` or ``.../home/<name>``
        prefix replaced by ``~``; unchanged when no home prefix is present.
    """
    return _HOME_PREFIX.sub("~", path)


def write_records_jsonl(records: Iterable[CallRecord], path: Path) -> int:
    """Write the normalized record stream as one JSON object per line.

    Each record's ``cwd`` and ``project`` are routed through :func:`redact_home`
    before serialization, so a home-rooted working directory lands in the file as
    a ``~``-prefixed path rather than a raw personal one, satisfying the plan's
    no-personal-paths contract for the artifact while keeping the project signal.

    Args:
        records: The records to serialize. Iterated once.
        path: The destination ``records.jsonl`` path; parent directories are
            created as needed.

    Returns:
        The number of records written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            redacted = record.model_copy(
                update={
                    "cwd": redact_home(record.cwd),
                    "project": redact_home(record.project),
                }
            )
            handle.write(redacted.model_dump_json())
            handle.write("\n")
            written += 1
    return written


def _verb_path_str(verb_path: tuple[str, ...]) -> str:
    """Render a verb path as a full ``vaultspec-core`` invocation string."""
    return " ".join([EXECUTABLE, *verb_path]) if verb_path else EXECUTABLE


def _section(title: str, lines: Sequence[str]) -> list[str]:
    """Render a titled section, with a placeholder when it has no rows."""
    body = list(lines) if lines else ["_none observed_"]
    return [f"## {title}", "", *body, ""]


def _hotspots_lines(records: Sequence[CallRecord]) -> list[str]:
    """Render the (a) verb-hotspots table."""
    rows = compute_hotspots(records)[:_TOP_N]
    return [f"- `{_verb_path_str(row.verb_path)}` - {row.count}" for row in rows]


def _ngram_lines(records: Sequence[CallRecord]) -> list[str]:
    """Render the (b) command-and-flag n-gram tables."""
    report = compute_ngrams(records)
    lines = ["### Repeated command-and-flag patterns", ""]
    if report.patterns:
        for pattern in report.patterns[:_TOP_N]:
            flags = " ".join(pattern.flags) if pattern.flags else "(no flags)"
            lines.append(
                f"- `{_verb_path_str(pattern.verb_path)}` {flags} - {pattern.count}"
            )
    else:
        lines.append("_none observed_")
    lines.extend(["", "### Flag co-occurrence", ""])
    if report.cooccurrences:
        for pair in report.cooccurrences[:_TOP_N]:
            lines.append(f"- `{pair.pair[0]}` + `{pair.pair[1]}` - {pair.count}")
    else:
        lines.append("_none observed_")
    return lines


def _features_lines(
    records: Sequence[CallRecord], inventory: CapabilityInventory
) -> list[str]:
    """Render the (c) features-utilized lists."""
    result = compute_features_utilized(records, inventory)
    lines = [
        f"Declared verb paths exercised: {len(result.utilized)}",
        "",
        "### Utilized (declared and used)",
        "",
    ]
    lines += [f"- `{_verb_path_str(path)}`" for path in result.utilized] or [
        "_none observed_"
    ]
    lines += ["", "### Observed but undeclared (candidate misses)", ""]
    lines += [f"- `{_verb_path_str(path)}`" for path in result.undeclared] or [
        "_none observed_"
    ]
    return lines


def _feature_tag_lines(records: Sequence[CallRecord]) -> list[str]:
    """Render the (d) feature-tag-usage distribution."""
    usage = compute_feature_tag_usage(records)
    lines = [
        f"Tagged invocations: {usage.tagged}; untagged: {usage.untagged}",
        "",
    ]
    lines += [f"- `{row.tag}` - {row.count}" for row in usage.counts[:_TOP_N]] or [
        "_none observed_"
    ]
    return lines


def _miss_lines(
    records: Sequence[CallRecord], inventory: CapabilityInventory
) -> list[str]:
    """Render the (e) tool-call-misses aggregate."""
    report = compute_misses(records, inventory)
    lines = [
        f"Genuine errors: {report.error_records} of {report.total_records} "
        f"records ({report.miss_rate:.1%} miss rate)",
        "",
        "### Errors by verb path",
        "",
    ]
    lines += [
        f"- `{_verb_path_str(row.verb_path)}` - {row.count}"
        for row in report.errors_by_verb[:_TOP_N]
    ] or ["_none observed_"]
    lines += ["", "### Undeclared-flag candidates (advisory)", ""]
    lines += [
        f"- `{_verb_path_str(row.verb_path)}` `{row.flag}` - {row.count}"
        for row in report.undeclared_flags[:_TOP_N]
    ] or ["_none observed_"]
    lines += ["", "### Retry corrections (errored call then re-flagged retry)", ""]
    lines += [
        f"- `{EXECUTABLE} {row.verb}` {' '.join(row.before_flags) or '(no flags)'}"
        f" -> {' '.join(row.after_flags) or '(no flags)'}"
        for row in report.retry_corrections[:_TOP_N]
    ] or ["_none observed_"]
    return lines


def _surface_lines(
    records: Sequence[CallRecord], inventory: CapabilityInventory
) -> list[str]:
    """Render the (f) overuse-and-dead-surface aggregate."""
    report = compute_surface(records, inventory)
    lines = [
        f"Declared surface coverage: {report.observed_declared_count} of "
        f"{report.declared_total} verb paths ({report.coverage:.1%})",
        "",
        "### Most-used declared verb paths (overuse)",
        "",
    ]
    lines += [
        f"- `{_verb_path_str(row.verb_path)}` - {row.count}"
        for row in report.observed_declared[:_TOP_N]
    ] or ["_none observed_"]
    lines += ["", "### Dead surface (declared, never invoked)", ""]
    lines += [f"- `{_verb_path_str(path)}`" for path in report.dead_surface] or [
        "_none observed_"
    ]
    lines += ["", "### Undeclared usage (observed, not in inventory)", ""]
    lines += [
        f"- `{_verb_path_str(row.verb_path)}` - {row.count}"
        for row in report.undeclared_usage[:_TOP_N]
    ] or ["_none observed_"]
    return lines


def _cost_lines(records: Sequence[CallRecord]) -> list[str]:
    """Render the (g) token-cost-per-class aggregate."""
    report = compute_cost(records)
    lines = [
        "Token cost is directional, not exact: the Claude side is a per-message "
        "approximation and the Codex side a snapshot-delta.",
        "",
        f"Total attributed token cost: {report.total_cost}",
        "",
        "### By source",
        "",
    ]
    lines += [
        f"- `{row.source}` - {row.total_cost} tokens across "
        f"{row.attributed_calls} attributed calls"
        for row in report.by_source
    ] or ["_none observed_"]
    lines += ["", "### By command class (verb)", ""]
    lines += [
        f"- `{EXECUTABLE} {row.verb or '(bare)'}` - {row.total_cost} tokens, "
        f"{row.attributed_calls}/{row.call_count} calls attributed"
        for row in report.by_verb[:_TOP_N]
    ] or ["_none observed_"]
    return lines


def render_report_markdown(
    records: Iterable[CallRecord],
    inventory: CapabilityInventory,
    window_days: int | None = None,
) -> str:
    """Render the seven metric families into an aggregate-only Markdown report.

    Args:
        records: The normalized records to report on. Materialized once.
        inventory: The declared-capability denominator the surface and miss
            metrics measure against.
        window_days: The activity window the corpus was filtered on, rendered in
            the header when supplied. Purely descriptive; it does not affect any
            aggregate.

    Returns:
        The complete report as a single Markdown string, carrying only
        aggregates, hashes, verb paths, tag values, counts, and costs.
    """
    snapshot = list(records)
    claude = sum(1 for record in snapshot if record.source == "claude")
    codex = sum(1 for record in snapshot if record.source == "codex")

    header = [
        "# vaultspec-core CLI usage analytics",
        "",
        f"Records analyzed: {len(snapshot)} ({claude} Claude, {codex} Codex).",
    ]
    if window_days is not None:
        header.append(f"Activity window: last {window_days} days.")
    header += [
        "",
        "This report carries only aggregates, hashes, verb paths, tag values, "
        "counts, and costs. No raw command body or personal path appears.",
        "",
    ]

    sections: list[str] = []
    sections += _section(
        "(a) Command and subcommand hotspots", _hotspots_lines(snapshot)
    )
    sections += _section("(b) Command and flag n-grams", _ngram_lines(snapshot))
    sections += _section("(c) Features utilized", _features_lines(snapshot, inventory))
    sections += _section("(d) Feature-tag usage", _feature_tag_lines(snapshot))
    sections += _section("(e) Tool-call misses", _miss_lines(snapshot, inventory))
    sections += _section(
        "(f) Overuse and dead surface", _surface_lines(snapshot, inventory)
    )
    sections += _section("(g) Token cost per command class", _cost_lines(snapshot))

    return "\n".join([*header, *sections]).rstrip() + "\n"


def write_report(
    records: Iterable[CallRecord],
    inventory: CapabilityInventory,
    path: Path,
    window_days: int | None = None,
) -> None:
    """Render and write the Markdown report to *path*.

    Args:
        records: The normalized records to report on.
        inventory: The declared-capability denominator.
        path: The destination ``report.md`` path; parents are created as needed.
        window_days: The activity window rendered in the header, when supplied.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_report_markdown(records, inventory, window_days)
    path.write_text(text, encoding="utf-8", newline="\n")
