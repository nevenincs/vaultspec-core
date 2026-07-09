"""The ``python -m statistic`` entrypoint wiring the full pipeline.

Running ``python -m statistic`` discovers both transcript corpora, normalizes
every in-window vaultspec-core invocation into one comparable
:class:`~statistic.normalize.models.CallRecord` stream, computes the seven metric
families, and writes the two artifacts into the gitignored ``statistic/out/``
directory: ``records.jsonl`` (the full record stream for re-analysis) and
``report.md`` (the aggregate-only human report).

Every input that varies by machine is a parameter with a home-derived default, so
nothing here hardcodes a username, drive letter, or calendar date. ``--claude-root``
and ``--codex-root`` default to the operator's ``~/.claude/projects`` and ``~/.codex``;
``--window-days`` defaults to 30 and filters on transcript activity timestamps at
runtime; ``--out`` defaults to the repo-relative ``statistic/out``. The declared-
capability denominator is parsed live from the CLI reference, defaulting to the
bundled ``.vaultspec/reference/cli.md``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from statistic.metrics.capability import (
    CapabilityInventory,
    default_reference_path,
    parse_capability_inventory,
)
from statistic.parsers.claude import ClaudeSource
from statistic.parsers.codex import CodexSource
from statistic.report.render import write_records_jsonl, write_report

if TYPE_CHECKING:
    from statistic.normalize.models import CallRecord

#: The default output directory, repo-relative so it carries no absolute prefix.
_DEFAULT_OUT = Path(__file__).resolve().parent / "out"


@dataclass(frozen=True)
class PipelineResult:
    """The outcome of one pipeline run.

    Attributes:
        records_written: The number of normalized records written to
            ``records.jsonl``.
        claude_records: How many of those records came from the Claude corpus.
        codex_records: How many came from the Codex corpus.
        records_path: The written ``records.jsonl`` path.
        report_path: The written ``report.md`` path.
    """

    records_written: int
    claude_records: int
    codex_records: int
    records_path: Path
    report_path: Path


def _collect_records(
    claude_root: Path | None,
    codex_root: Path | None,
    window_days: int,
    inventory: CapabilityInventory,
) -> list[CallRecord]:
    """Stream and materialize every in-window record from both corpora.

    Args:
        claude_root: The Claude projects root, or ``None`` for the home default.
        codex_root: The Codex home root, or ``None`` for the home default.
        window_days: The activity-window width the adapters filter on.
        inventory: The declared-capability denominator for verb-path resolution.

    Returns:
        Every normalized record from both sources, Claude first then Codex.
    """
    records: list[CallRecord] = []
    claude = ClaudeSource(
        root=claude_root, window_days=window_days, inventory=inventory
    )
    for claude_session in claude.iter_sessions():
        records.extend(claude.iter_calls(claude_session))
    codex = CodexSource(root=codex_root, window_days=window_days, inventory=inventory)
    for codex_session in codex.iter_sessions():
        records.extend(codex.iter_calls(codex_session))
    return records


def run_pipeline(
    claude_root: Path | None = None,
    codex_root: Path | None = None,
    window_days: int = 30,
    out_dir: Path = _DEFAULT_OUT,
    reference_path: Path | None = None,
) -> PipelineResult:
    """Run the full analytics pipeline and write both artifacts.

    Args:
        claude_root: The Claude projects root, or ``None`` for
            ``~/.claude/projects``.
        codex_root: The Codex home root, or ``None`` for ``~/.codex``.
        window_days: The activity-window width in days.
        out_dir: The directory both artifacts are written into; created as
            needed.
        reference_path: The CLI reference to parse the denominator from, or
            ``None`` for the bundled default.

    Returns:
        The :class:`PipelineResult` describing what was written.
    """
    inventory = parse_capability_inventory(
        reference_path if reference_path is not None else default_reference_path()
    )
    records = _collect_records(claude_root, codex_root, window_days, inventory)

    records_path = out_dir / "records.jsonl"
    report_path = out_dir / "report.md"
    write_records_jsonl(records, records_path)
    write_report(records, inventory, report_path, window_days)

    return PipelineResult(
        records_written=len(records),
        claude_records=sum(1 for record in records if record.source == "claude"),
        codex_records=sum(1 for record in records if record.source == "codex"),
        records_path=records_path,
        report_path=report_path,
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser.

    Returns:
        The configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="python -m statistic",
        description=(
            "Analyze the Claude Code and Codex transcript corpora into the "
            "seven vaultspec-core CLI usage metric families."
        ),
    )
    parser.add_argument(
        "--claude-root",
        type=Path,
        default=None,
        help="Claude projects root (default: ~/.claude/projects).",
    )
    parser.add_argument(
        "--codex-root",
        type=Path,
        default=None,
        help="Codex home root (default: $CODEX_HOME or ~/.codex).",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="Activity window width in days (default: 30).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output directory for records.jsonl and report.md "
        "(default: statistic/out).",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="CLI reference to parse the capability denominator from "
        "(default: bundled .vaultspec/reference/cli.md).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the pipeline, and print a summary.

    Args:
        argv: The argument vector, or ``None`` to read ``sys.argv``.

    Returns:
        The process exit code, ``0`` on success.
    """
    args = build_parser().parse_args(argv)
    result = run_pipeline(
        claude_root=args.claude_root,
        codex_root=args.codex_root,
        window_days=args.window_days,
        out_dir=args.out,
        reference_path=args.reference,
    )
    print(
        f"Wrote {result.records_written} records "
        f"({result.claude_records} Claude, {result.codex_records} Codex)."
    )
    print(f"  records: {result.records_path}")
    print(f"  report:  {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
