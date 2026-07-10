"""End-to-end tests for the ``python -m statistic`` pipeline entrypoint.

The pipeline is driven against fully synthetic Claude and Codex fixture trees
built under real temporary directories at test time, and the committed redacted
CLI-reference fixture. No test touches the operator's ``~/.claude`` or ``~/.codex``,
no username or absolute machine path appears, and the only date used is a
timezone-aware ``now`` offset so the window filter admits the synthetic records
deterministically. The pipeline is exercised through :func:`run_pipeline` with
every root injected, so it wires source discovery, normalization, metrics, and
report rendering into both on-disk artifacts without machine dependence.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from statistic.__main__ import build_parser, run_pipeline

if TYPE_CHECKING:
    from collections.abc import Iterator

_REFERENCE = Path(__file__).parent / "fixtures" / "cli_reference.md"
_IN_WINDOW = datetime.now(tz=UTC) - timedelta(days=2)


@pytest.fixture
def roots() -> Iterator[tuple[Path, Path, Path]]:
    """Yield isolated ``(claude_root, codex_root, out_dir)`` scratch paths."""
    with (
        tempfile.TemporaryDirectory() as claude,
        tempfile.TemporaryDirectory() as codex,
        tempfile.TemporaryDirectory() as out,
    ):
        yield Path(claude), Path(codex), Path(out)


def _claude_line(kind: str, message: dict[str, Any], **top: Any) -> str:
    """Render one Claude transcript line."""
    return json.dumps(
        {
            "type": kind,
            "timestamp": _IN_WINDOW.isoformat().replace("+00:00", "Z"),
            "message": message,
            **top,
        }
    )


def _build_claude(root: Path) -> None:
    """Write a minimal synthetic Claude project transcript under *root*."""
    project = root / "proj-slug"
    project.mkdir(parents=True)
    lines = [
        _claude_line(
            "assistant",
            {
                "model": "claude-x",
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Bash",
                        "input": {
                            "command": (
                                "cd /work && uv run --no-sync "
                                "vaultspec-core vault list --feature mcp"
                            )
                        },
                    }
                ],
            },
            sessionId="claude-1",
            cwd="/work/proj",
            gitBranch="feature/mcp",
            version="1.2.3",
        ),
        _claude_line(
            "user",
            {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "is_error": False,
                        "content": "ok",
                    }
                ]
            },
        ),
    ]
    (project / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _codex_line(kind: str, payload: dict[str, Any]) -> str:
    """Render one Codex rollout line."""
    return json.dumps(
        {
            "timestamp": _IN_WINDOW.isoformat().replace("+00:00", "Z"),
            "type": kind,
            "payload": payload,
        }
    )


def _build_codex(root: Path) -> None:
    """Write a minimal synthetic Codex rollout under *root*."""
    sessions = root / "sessions" / "cycle" / "batch"
    sessions.mkdir(parents=True)
    arguments = json.dumps(
        {"command": "vaultspec-core status feat", "workdir": "/work"}
    )
    lines = [
        _codex_line(
            "session_meta",
            {"session_id": "codex-1", "cwd": "/work/proj", "cli_version": "5.5.0"},
        ),
        _codex_line("turn_context", {"cwd": "/work/proj", "model": "gpt-5.5"}),
        _codex_line(
            "response_item",
            {
                "type": "function_call",
                "name": "shell_command",
                "arguments": arguments,
                "call_id": "call-1",
            },
        ),
        _codex_line(
            "response_item",
            {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": "Exit code: 0\nWall time: 0.1s\nOutput:\ndone",
            },
        ),
    ]
    (sessions / "rollout-main.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def test_pipeline_writes_both_artifacts(roots: tuple[Path, Path, Path]) -> None:
    """The pipeline emits records.jsonl and report.md over both corpora."""
    claude_root, codex_root, out = roots
    _build_claude(claude_root)
    _build_codex(codex_root)

    result = run_pipeline(
        claude_root=claude_root,
        codex_root=codex_root,
        window_days=30,
        out_dir=out,
        reference_path=_REFERENCE,
    )

    assert result.records_written == 2
    assert result.claude_records == 1
    assert result.codex_records == 1
    assert result.records_path.is_file()
    assert result.report_path.is_file()


def test_records_jsonl_holds_both_sources(roots: tuple[Path, Path, Path]) -> None:
    """Both a Claude and a Codex record land in the stream, hashes only."""
    claude_root, codex_root, out = roots
    _build_claude(claude_root)
    _build_codex(codex_root)

    run_pipeline(
        claude_root=claude_root,
        codex_root=codex_root,
        out_dir=out,
        reference_path=_REFERENCE,
    )
    lines = (out / "records.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    assert {obj["source"] for obj in parsed} == {"claude", "codex"}
    assert all("command" not in obj for obj in parsed)
    assert all(obj["command_hash"] for obj in parsed)


def test_report_md_renders_sections(roots: tuple[Path, Path, Path]) -> None:
    """The generated report names the metric families and the record count."""
    claude_root, codex_root, out = roots
    _build_claude(claude_root)
    _build_codex(codex_root)

    run_pipeline(
        claude_root=claude_root,
        codex_root=codex_root,
        out_dir=out,
        reference_path=_REFERENCE,
    )
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "# vaultspec-core CLI usage analytics" in report
    assert "Records analyzed: 2 (1 Claude, 1 Codex)." in report
    assert "(a) Command and subcommand hotspots" in report
    assert "(g) Token cost per command class" in report


def test_empty_corpora_still_write_artifacts(roots: tuple[Path, Path, Path]) -> None:
    """With no transcripts the pipeline writes an empty stream and a report."""
    _claude_root, _codex_root, out = roots
    result = run_pipeline(
        claude_root=out / "no-claude",
        codex_root=out / "no-codex",
        out_dir=out,
        reference_path=_REFERENCE,
    )
    assert result.records_written == 0
    assert result.records_path.read_text(encoding="utf-8") == ""
    assert result.report_path.is_file()


def test_parser_defaults_are_home_derived() -> None:
    """The CLI parser defaults the roots to None so the sources derive home."""
    args = build_parser().parse_args([])
    assert args.claude_root is None
    assert args.codex_root is None
    assert args.window_days == 30
