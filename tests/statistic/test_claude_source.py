"""Tests for the Claude Code project-transcript source adapter.

The fixture tree is fully synthetic and built under a temporary root at test
time: a fake ``projects/<slug>/*.jsonl`` transcript plus a
``subagents/agent-<role>.jsonl`` subagent transcript, with invented session ids,
abstract ``/work/proj`` working directories, and per-line timestamps computed
*relative to now* (an in-window ``now - 2 days`` and an out-of-window
``now - 45 days``). No username, absolute machine path, or hardcoded calendar
date appears anywhere, and the window filter is exercised deterministically
without pinning a date. Every transcript line is spelled out literally so the
assertions pin exactly what the adapter parses.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from statistic.metrics.capability import (
    CapabilityInventory,
    parse_capability_inventory,
)
from statistic.normalize.exit_status import ExitStatus
from statistic.parsers.claude import ClaudeSource

if TYPE_CHECKING:
    from collections.abc import Iterator

    from statistic.normalize.models import CallRecord


@pytest.fixture
def work_root() -> Iterator[Path]:
    """A real, isolated scratch directory for a synthetic corpus tree.

    Uses stdlib :func:`tempfile.TemporaryDirectory` rather than the ``tmp_path``
    fixture so the test exercises the real filesystem independently of pytest's
    temp-dir plumbing.
    """
    with tempfile.TemporaryDirectory() as name:
        yield Path(name)


_CLI_REFERENCE = Path(__file__).parent / "fixtures" / "cli_reference.md"

_IN_WINDOW = datetime.now(tz=UTC) - timedelta(days=2)
_OUT_OF_WINDOW = datetime.now(tz=UTC) - timedelta(days=45)


def _inventory() -> CapabilityInventory:
    """Parse the committed capability fixture into an inventory."""
    return parse_capability_inventory(_CLI_REFERENCE)


def _assistant(
    timestamp: datetime,
    tool_uses: list[dict[str, Any]],
    *,
    usage: dict[str, int] | None = None,
    session_id: str = "sess-main",
) -> str:
    """Render one assistant transcript line carrying shell tool calls."""
    message: dict[str, Any] = {
        "model": "synthetic-model",
        "content": [{"type": "text", "text": "narrative"}, *tool_uses],
    }
    if usage is not None:
        message["usage"] = usage
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": timestamp.isoformat(),
            "cwd": "/work/proj",
            "gitBranch": "work",
            "sessionId": session_id,
            "parentUuid": "parent-uuid-1",
            "uuid": "line-uuid",
            "version": "9.9.9",
            "message": message,
        }
    )


def _tool_use(tool_use_id: str, command: str, *, name: str = "Bash") -> dict[str, Any]:
    """Render one ``tool_use`` content entry."""
    return {
        "type": "tool_use",
        "id": tool_use_id,
        "name": name,
        "input": {"command": command, "description": "synthetic"},
    }


def _result(timestamp: datetime, tool_use_id: str, text: str, *, is_error: bool) -> str:
    """Render one user transcript line carrying a linked ``tool_result``."""
    return json.dumps(
        {
            "type": "user",
            "timestamp": timestamp.isoformat(),
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": text,
                        "is_error": is_error,
                    }
                ]
            },
        }
    )


#: A realistic non-fatal setuptools ``.pth`` traceback ``uv run`` prints to
#: stderr around an otherwise-successful command.
_VENV_NOISE = (
    "Error processing line 1 of /venv/lib/site-packages/distutils-precedence.pth:\n"
    "\n"
    "  Traceback (most recent call last):\n"
    '    File "<string>", line 1, in <module>\n'
    "  ImportError: cannot import name something\n"
    "\n"
    "Remainder of file ignored\n"
    "vault list ran successfully"
)


def _build_corpus(root: Path) -> None:
    """Write the synthetic Claude project tree under *root*."""
    project = root / "projects" / "work-proj"
    project.mkdir(parents=True)
    subagents = project / "subagents"
    subagents.mkdir()

    # Lines are chronological (oldest first), as append-only transcripts are: the
    # out-of-window turn precedes the in-window turns so the per-line window
    # filter, not file order, decides admission.
    main_lines = [
        json.dumps({"type": "summary", "summary": "session header, no timestamp"}),
        _assistant(
            _OUT_OF_WINDOW,
            [_tool_use("toolu-old", "uv run --no-sync vaultspec-core status feat")],
        ),
        _result(_OUT_OF_WINDOW, "toolu-old", "oriented", is_error=False),
        _assistant(
            _IN_WINDOW,
            [_tool_use("toolu-status", "uv run --no-sync vaultspec-core status feat")],
            usage={"input_tokens": 60, "output_tokens": 40},
        ),
        _result(_IN_WINDOW, "toolu-status", "oriented", is_error=False),
        _assistant(
            _IN_WINDOW,
            [
                _tool_use("toolu-multi-a", "uv run --no-sync vaultspec-core status"),
                _tool_use("toolu-multi-b", "uv run --no-sync vaultspec-core sync"),
            ],
            usage={"input_tokens": 100, "output_tokens": 100},
        ),
        _result(_IN_WINDOW, "toolu-multi-a", "oriented", is_error=False),
        _result(_IN_WINDOW, "toolu-multi-b", "synced", is_error=False),
        _assistant(
            _IN_WINDOW,
            [
                _tool_use(
                    "toolu-check", "uv run --no-sync vaultspec-core vault check all"
                )
            ],
        ),
        _result(
            _IN_WINDOW, "toolu-check", "Found 3 issues; run with --fix", is_error=True
        ),
        _assistant(
            _IN_WINDOW,
            [_tool_use("toolu-venv", "uv run --no-sync vaultspec-core vault list")],
        ),
        _result(_IN_WINDOW, "toolu-venv", _VENV_NOISE, is_error=False),
        _assistant(
            _IN_WINDOW,
            [_tool_use("toolu-error", "uv run --no-sync vaultspec-core vault list")],
        ),
        _result(
            _IN_WINDOW,
            "toolu-error",
            "No such command 'lst'\nUsage: vaultspec-core vault ...",
            is_error=True,
        ),
    ]
    (project / "session-main.jsonl").write_text(
        "\n".join(main_lines) + "\n", encoding="utf-8"
    )

    sub_lines = [
        json.dumps({"type": "summary", "summary": "subagent header"}),
        _assistant(
            _IN_WINDOW,
            [_tool_use("toolu-sub", "uv run --no-sync vaultspec-core vault list")],
            session_id="sess-sub",
        ),
        _result(_IN_WINDOW, "toolu-sub", "listed", is_error=False),
    ]
    (subagents / "agent-code-reviewer.jsonl").write_text(
        "\n".join(sub_lines) + "\n", encoding="utf-8"
    )


def _collect(root: Path) -> list[CallRecord]:
    """Discover and normalize every record under a synthetic corpus root."""
    source = ClaudeSource(root=root / "projects", inventory=_inventory())
    records: list[CallRecord] = []
    for session in source.iter_sessions():
        records.extend(source.iter_calls(session))
    return records


def test_claude_source_parses_expected_record_set(work_root: Path) -> None:
    """The adapter yields one in-window record per shell call, old lines aside."""
    _build_corpus(work_root)
    records = _collect(work_root)
    subcommands = sorted(r.subcommand for r in records)
    assert subcommands == sorted(
        [
            ("status",),
            ("status",),
            ("sync",),
            ("vault", "check", "all"),
            ("vault", "list"),
            ("vault", "list"),
            ("vault", "list"),
        ]
    )
    assert all(r.source == "claude" for r in records)
    assert all(r.timestamp >= _OUT_OF_WINDOW + timedelta(days=1) for r in records)


def test_out_of_window_line_is_excluded(work_root: Path) -> None:
    """The ``now - 45d`` call is dropped while its in-window siblings survive."""
    _build_corpus(work_root)
    records = _collect(work_root)
    assert all(r.retry_key != "toolu-old" for r in records)
    assert not any(
        r.timestamp < datetime.now(tz=UTC) - timedelta(days=30) for r in records
    )
    assert len(records) == 7


def test_multi_tool_use_message_splits_token_cost(work_root: Path) -> None:
    """The two-call message's 200-token usage is split evenly into 100 each."""
    _build_corpus(work_root)
    records = _collect(work_root)
    multi = [r for r in records if r.subcommand in {("status",), ("sync",)}]
    split = [r for r in multi if r.token_cost == 100]
    assert {r.subcommand for r in split} >= {("status",), ("sync",)}
    single = next(
        r for r in records if r.subcommand == ("status",) and r.token_cost == 100
    )
    assert single.token_cost == 100


def test_is_error_result_maps_to_error(work_root: Path) -> None:
    """A genuine ``is_error`` result on ``vault list`` maps to ERROR."""
    _build_corpus(work_root)
    records = _collect(work_root)
    errored = [r for r in records if r.exit_status is ExitStatus.ERROR]
    assert [r.subcommand for r in errored] == [("vault", "list")]


def test_by_design_finding_maps_to_findings_not_error(work_root: Path) -> None:
    """An errored ``vault check all`` is a finding, never a miss."""
    _build_corpus(work_root)
    records = _collect(work_root)
    check = next(r for r in records if r.subcommand == ("vault", "check", "all"))
    assert check.exit_status is ExitStatus.FINDINGS


def test_distutils_noise_line_is_not_an_error(work_root: Path) -> None:
    """The setuptools ``.pth`` traceback never inflates the miss rate."""
    _build_corpus(work_root)
    records = _collect(work_root)
    noisy = [
        r
        for r in records
        if r.subcommand == ("vault", "list")
        and r.session_id == "sess-main"
        and r.exit_status is ExitStatus.OK
    ]
    assert len(noisy) == 1


def test_for_loop_message_cost_splits_across_expanded_records(
    work_root: Path,
) -> None:
    """A 300-token message whose single call is a 3-iteration loop costs 100 each.

    The physical message emits one ``tool_use`` carrying a ``for`` loop that
    expands into three logical records. Its 300-token usage must be divided by
    the three expanded records - 100 each, 300 total - not attributed in full to
    each record, which would triple the cost to 900.
    """
    project = work_root / "projects" / "loop-proj"
    project.mkdir(parents=True)
    loop_command = (
        "for s in S01 S02 S03; do "
        "uv run --no-sync vaultspec-core vault plan step check PLAN $s; done"
    )
    line = _assistant(
        _IN_WINDOW,
        [_tool_use("toolu-loop", loop_command)],
        usage={"input_tokens": 300, "output_tokens": 0},
    )
    (project / "session-loop.jsonl").write_text(line + "\n", encoding="utf-8")

    source = ClaudeSource(root=work_root / "projects", inventory=_inventory())
    records = [
        record
        for session in source.iter_sessions()
        for record in source.iter_calls(session)
    ]
    assert len(records) == 3
    assert all(r.subcommand == ("vault", "plan", "step", "check") for r in records)
    assert [r.token_cost for r in records] == [100, 100, 100]
    assert sum(r.token_cost or 0 for r in records) == 300


def test_subagent_transcript_attributes_role(work_root: Path) -> None:
    """The subagent transcript carries its role while parent turns do not."""
    _build_corpus(work_root)
    records = _collect(work_root)
    sub = [r for r in records if r.subagent_role is not None]
    assert len(sub) == 1
    assert sub[0].subagent_role == "code-reviewer"
    assert sub[0].subcommand == ("vault", "list")
    assert all(r.subagent_role is None for r in records if r.session_id == "sess-main")
