"""Tests for the ``records.jsonl`` and ``report.md`` renderers.

Records are built in code, never read from a transcript, so the assertions
depend on no machine state, username, absolute path, or wall-clock date beyond a
fixed timezone-aware anchor the model requires. The privacy contract is asserted
directly: the rendered report must carry the aggregates it promises while never
surfacing a raw command body or a home path, and the JSONL stream must retain the
command only as its hash. A real temporary directory (stdlib ``tempfile``, not
the ``tmp_path`` fixture) exercises the on-disk writers.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from statistic.metrics.capability import CapabilityInventory
from statistic.normalize.exit_status import ExitStatus
from statistic.normalize.models import CallRecord
from statistic.report.render import (
    redact_home,
    render_report_markdown,
    write_records_jsonl,
    write_report,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_ANCHOR = datetime(2000, 1, 1, tzinfo=UTC)


def _record(
    verb_path: tuple[str, ...],
    *,
    flags: dict[str, str | bool] | None = None,
    feature_tag: str | None = None,
    exit_status: ExitStatus = ExitStatus.OK,
    token_cost: int | None = None,
    source: Literal["claude", "codex"] = "claude",
    cwd: str = "/work/proj",
    order: int = 0,
) -> CallRecord:
    """Build one synthetic record for renderer assertions."""
    return CallRecord(
        source=source,
        session_id="s1",
        timestamp=_ANCHOR.replace(minute=order % 60),
        project="proj",
        cwd=cwd,
        verb=verb_path[0] if verb_path else "",
        subcommand=verb_path,
        flags=flags if flags is not None else {},
        feature_tag=feature_tag,
        command_hash=f"deadbeef{order:04d}",
        exit_status=exit_status,
        token_cost=token_cost,
    )


def _inventory() -> CapabilityInventory:
    """A small declared-capability denominator for the renderer tests."""
    return CapabilityInventory(
        verb_paths=frozenset(
            {("vault", "list"), ("vault", "add"), ("vault", "check", "all"), ("sync",)}
        ),
        flags={("vault", "add"): frozenset({"--feature", "--step"})},
    )


def _records() -> list[CallRecord]:
    """A representative record set touching every metric family."""
    return [
        _record(("vault", "list"), token_cost=10, order=0),
        _record(("vault", "list"), token_cost=20, order=1),
        _record(
            ("vault", "add"),
            flags={"--feature": "mcp", "--step": "S01"},
            feature_tag="mcp",
            token_cost=100,
            order=2,
        ),
        _record(
            ("vault", "check", "all"),
            exit_status=ExitStatus.FINDINGS,
            token_cost=50,
            order=3,
        ),
        _record(
            ("vault", "nonexistent"),
            exit_status=ExitStatus.ERROR,
            source="codex",
            token_cost=5,
            order=4,
        ),
    ]


def _out_dir() -> Iterator[Path]:
    """Yield a real, isolated scratch directory for the on-disk writers.

    Uses stdlib :func:`tempfile.TemporaryDirectory` rather than the ``tmp_path``
    fixture so the writers touch the real filesystem independently of pytest's
    temp-dir plumbing.
    """
    with tempfile.TemporaryDirectory() as name:
        yield Path(name)


def test_records_jsonl_round_trips_without_raw_command() -> None:
    """Every record serializes one-per-line, carrying a hash but no raw command."""
    records = _records()
    for out in _out_dir():
        path = out / "records.jsonl"
        written = write_records_jsonl(records, path)
        assert written == len(records)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == len(records)
        for line in lines:
            obj = json.loads(line)
            assert "command_hash" in obj
            assert "command" not in obj
            assert obj["command_hash"].startswith("deadbeef")


def test_report_renders_all_seven_families() -> None:
    """The report names each of the seven metric families as a section."""
    report = render_report_markdown(_records(), _inventory(), window_days=30)
    for marker in (
        "(a) Command and subcommand hotspots",
        "(b) Command and flag n-grams",
        "(c) Features utilized",
        "(d) Feature-tag usage",
        "(e) Tool-call misses",
        "(f) Overuse and dead surface",
        "(g) Token cost per command class",
    ):
        assert marker in report


def test_report_contains_expected_aggregates() -> None:
    """Key aggregate values render into the report body."""
    report = render_report_markdown(_records(), _inventory(), window_days=30)
    # hotspots: vault list observed twice.
    assert "`vaultspec-core vault list` - 2" in report
    # miss rate: one genuine error out of five records.
    assert "1 of 5 records (20.0% miss rate)" in report
    # dead surface: sync declared but never invoked.
    assert "`vaultspec-core sync`" in report
    # feature-tag distribution.
    assert "`mcp` - 1" in report
    # window header.
    assert "Activity window: last 30 days." in report


def test_findings_exit_is_not_counted_as_a_miss() -> None:
    """A by-design findings record never enters the miss count."""
    report = render_report_markdown(_records(), _inventory())
    # only the single ERROR record counts; the FINDINGS check does not.
    assert "1 of 5 records" in report


def test_report_leaks_no_home_path() -> None:
    """A home-path cwd on a record never reaches the rendered report."""
    records = [
        _record(("vault", "list"), cwd="C:/Users/someone/secret/work", order=0),
    ]
    report = render_report_markdown(records, _inventory())
    assert "someone" not in report
    assert "secret" not in report


def test_write_report_persists_markdown() -> None:
    """The report writer materializes the rendered document on disk."""
    for out in _out_dir():
        path = out / "report.md"
        write_report(_records(), _inventory(), path, window_days=30)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# vaultspec-core CLI usage analytics")
        assert text.endswith("\n")


def test_redact_home_collapses_user_prefix() -> None:
    """The home-path redactor collapses both separator styles to ``~``."""
    assert redact_home("C:/Users/someone/proj") == "~/proj"
    assert redact_home("/home/someone/proj") == "~/proj"
    assert redact_home("relative/path") == "relative/path"
