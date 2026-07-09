"""Tests for the Codex rollout-session source adapter.

The fixture tree is fully synthetic and built under a temporary root at test
time: a fake ``sessions/<cycle>/<batch>/rollout-*.jsonl`` rollout plus an
``archived_sessions/rollout-*.jsonl`` subagent rollout, with invented session
ids, abstract ``/work/proj`` working directories, JSON-string ``arguments``
payloads, and per-line timestamps computed *relative to now* (an in-window
``now - 2 days`` and an out-of-window ``now - 45 days``). No username, absolute
machine path, or hardcoded calendar date appears anywhere; the directory names
under ``sessions`` are neutral synthetic labels, not dates, so the window filter
is exercised deterministically without pinning a date.
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
from statistic.parsers.codex import CodexSource

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


def _line(timestamp: datetime, kind: str, payload: dict[str, Any]) -> str:
    """Render one rollout line as ``{timestamp,type,payload}``."""
    return json.dumps(
        {"timestamp": timestamp.isoformat(), "type": kind, "payload": payload}
    )


def _function_call(timestamp: datetime, call_id: str, command: str) -> str:
    """Render a ``function_call`` line with a JSON-string ``arguments`` field."""
    arguments = json.dumps(
        {"command": command, "workdir": "/work/proj", "timeout_ms": 1000}
    )
    return _line(
        timestamp,
        "response_item",
        {
            "type": "function_call",
            "name": "shell_command",
            "arguments": arguments,
            "call_id": call_id,
        },
    )


def _function_output(timestamp: datetime, call_id: str, exit_code: int) -> str:
    """Render the paired ``function_call_output`` carrying an explicit exit code."""
    output = f"Exit code: {exit_code}\nWall time: 0.1s\nOutput:\ndone"
    return _line(
        timestamp,
        "response_item",
        {"type": "function_call_output", "call_id": call_id, "output": output},
    )


def _token_count(timestamp: datetime, total: int) -> str:
    """Render a cumulative ``token_count`` snapshot line."""
    return _line(
        timestamp,
        "event_msg",
        {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input": total,
                    "output": 0,
                    "total": total,
                }
            },
        },
    )


def _build_corpus(root: Path) -> None:
    """Write the synthetic Codex rollout tree under *root*."""
    sessions = root / "sessions" / "cycle" / "batch"
    sessions.mkdir(parents=True)
    archived = root / "archived_sessions"
    archived.mkdir()

    main_lines = [
        _line(
            _IN_WINDOW,
            "session_meta",
            {
                "session_id": "codex-main",
                "cwd": "/work/proj",
                "cli_version": "5.5.0",
                "originator": "cli",
            },
        ),
        _line(_IN_WINDOW, "turn_context", {"cwd": "/work/proj", "model": "gpt-5.5"}),
        _token_count(_IN_WINDOW, 1000),
        _function_call(
            _IN_WINDOW, "call-1", "uv run --no-sync vaultspec-core vault list"
        ),
        _function_output(_IN_WINDOW, "call-1", 0),
        _token_count(_IN_WINDOW, 1100),
        _function_call(
            _IN_WINDOW, "call-2", "uv run --no-sync vaultspec-core vault check all"
        ),
        _function_output(_IN_WINDOW, "call-2", 1),
        _token_count(_IN_WINDOW, 1250),
        _function_call(
            _IN_WINDOW, "call-3", "uv run --no-sync vaultspec-core vault list"
        ),
        _function_output(_IN_WINDOW, "call-3", 2),
        _token_count(_IN_WINDOW, 1400),
        _function_call(
            _OUT_OF_WINDOW, "call-old", "uv run --no-sync vaultspec-core status feat"
        ),
        _function_output(_OUT_OF_WINDOW, "call-old", 0),
    ]
    (sessions / "rollout-main.jsonl").write_text(
        "\n".join(main_lines) + "\n", encoding="utf-8"
    )

    sub_lines = [
        _line(
            _IN_WINDOW,
            "session_meta",
            {
                "session_id": "codex-sub",
                "cwd": "/work/proj",
                "cli_version": "5.5.0",
                "thread_source": "subagent",
                "agent_role": "vaultspec-code-reviewer",
                "source": {"subagent": {"nickname": "reviewer"}},
            },
        ),
        _line(_IN_WINDOW, "turn_context", {"cwd": "/work/proj", "model": "gpt-5.5"}),
        _function_call(
            _IN_WINDOW, "call-sub", "uv run --no-sync vaultspec-core vault list"
        ),
        _function_output(_IN_WINDOW, "call-sub", 0),
    ]
    (archived / "rollout-sub.jsonl").write_text(
        "\n".join(sub_lines) + "\n", encoding="utf-8"
    )


def _collect(root: Path) -> list[CallRecord]:
    """Discover and normalize every record under a synthetic corpus root."""
    source = CodexSource(root=root, inventory=_inventory())
    records: list[CallRecord] = []
    for session in source.iter_sessions():
        records.extend(source.iter_calls(session))
    return records


def _main_records(root: Path) -> dict[str, CallRecord]:
    """Return the main-session records keyed by their linking call id."""
    return {
        r.retry_key: r
        for r in _collect(root)
        if r.session_id == "codex-main" and r.retry_key is not None
    }


def test_codex_source_parses_expected_record_set(work_root: Path) -> None:
    """Every in-window shell call yields a record; the old call is dropped."""
    _build_corpus(work_root)
    records = _collect(work_root)
    assert all(r.source == "codex" for r in records)
    assert all(r.git_branch is None for r in records)
    assert all(r.model == "gpt-5.5" for r in records)
    assert all(r.cli_version == "5.5.0" for r in records)
    # three main-session calls plus one archived subagent call, old call excluded.
    assert len(records) == 4


def test_json_string_arguments_are_decoded(work_root: Path) -> None:
    """The JSON-string ``arguments`` field is decoded to reach the command."""
    _build_corpus(work_root)
    by_call = _main_records(work_root)
    assert by_call["call-1"].subcommand == ("vault", "list")
    assert by_call["call-2"].subcommand == ("vault", "check", "all")
    assert by_call["call-1"].cwd == "/work/proj"
    assert by_call["call-1"].project == "proj"


def test_exit_codes_map_onto_status_vocabulary(work_root: Path) -> None:
    """0 is ok, by-design 1 is findings, other non-zero is error; codes stored."""
    _build_corpus(work_root)
    by_call = _main_records(work_root)
    assert by_call["call-1"].exit_status is ExitStatus.OK
    assert by_call["call-1"].raw_exit_code == 0
    assert by_call["call-2"].exit_status is ExitStatus.FINDINGS
    assert by_call["call-2"].raw_exit_code == 1
    assert by_call["call-3"].exit_status is ExitStatus.ERROR
    assert by_call["call-3"].raw_exit_code == 2


def test_token_cost_from_snapshot_deltas(work_root: Path) -> None:
    """Each call's cost is the delta of the snapshots bracketing it."""
    _build_corpus(work_root)
    by_call = _main_records(work_root)
    assert by_call["call-1"].token_cost == 100
    assert by_call["call-2"].token_cost == 150
    assert by_call["call-3"].token_cost == 150


def test_out_of_window_line_is_excluded(work_root: Path) -> None:
    """The ``now - 45d`` call is filtered out while in-window calls survive."""
    _build_corpus(work_root)
    by_call = _main_records(work_root)
    assert "call-old" not in by_call
    assert set(by_call) == {"call-1", "call-2", "call-3"}


def test_subagent_role_from_session_meta(work_root: Path) -> None:
    """An archived subagent rollout attributes its ``agent_role``."""
    _build_corpus(work_root)
    records = _collect(work_root)
    sub = [r for r in records if r.subagent_role is not None]
    assert len(sub) == 1
    assert sub[0].subagent_role == "vaultspec-code-reviewer"
    assert sub[0].session_id == "codex-sub"
