"""Integration tests for ``vault exec log``, the consolidated-ledger writer.

Covers first-use creation, append-only accumulation across Steps, idempotent
re-logging, rename and delete rows, malformed ``--row`` refusal, and the
round-trip that matters: a logged Step must map back through the shared
execution-record index exactly as a per-Step record would.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

from vaultspec_core.cli import app

from .test_step_aware_exec import setup_test_plan

pytestmark = [pytest.mark.integration]

_PLAN_STEM = "2026-05-17-test-feature-plan"
_LEDGER = "2026-05-17-test-feature/2026-05-17-test-feature-ledger.md"


def _log(runner: CliRunner, project: Path, step: str, *rows: str):
    args = [
        "--target",
        str(project),
        "vault",
        "exec",
        "log",
        "--feature",
        "test-feature",
        "--related",
        _PLAN_STEM,
        "--step",
        step,
    ]
    for spec in rows:
        args += ["--row", spec]
    return runner.invoke(app, args)


def _ledger_text(project: Path) -> str:
    return (project / ".vault" / "exec" / _LEDGER).read_text(encoding="utf-8")


def test_first_log_creates_the_ledger(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)

    result = _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")

    assert result.exit_code == 0, result.output
    text = _ledger_text(synthetic_project)
    assert "- `S01` `M` `src/foo.py`" in text
    assert "body_schema: 'body-v2'" in text
    assert f"[[{_PLAN_STEM}]]" in text


def test_second_step_appends_without_rewriting_the_first(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)

    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")
    result = _log(runner, synthetic_project, "P01.S02", "A:src/bar.py")

    assert result.exit_code == 0, result.output
    text = _ledger_text(synthetic_project)
    assert text.index("- `S01` `M` `src/foo.py`") < text.index(
        "- `S02` `A` `src/bar.py`"
    )
    # One document, both Steps.
    assert text.count("## Changes") == 1


def test_relogging_the_same_row_is_idempotent(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)

    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")
    before = _ledger_text(synthetic_project)
    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")

    assert _ledger_text(synthetic_project) == before


def test_rename_and_delete_rows(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)

    result = _log(
        runner,
        synthetic_project,
        "P01.S01",
        "R:src/old.py->src/new.py",
        "D:src/gone.py",
    )

    assert result.exit_code == 0, result.output
    text = _ledger_text(synthetic_project)
    assert "- `S01` `R` `src/old.py` -> `src/new.py`" in text
    assert "- `S01` `D` `src/gone.py`" in text


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("src/foo.py", "expected 'OP:path'"),
        ("X:src/foo.py", "unknown operation"),
        ("R:src/only.py", "a rename needs"),
    ],
)
def test_malformed_row_is_refused(
    runner: CliRunner, synthetic_project: Path, spec: str, expected: str
) -> None:
    setup_test_plan(synthetic_project)

    result = _log(runner, synthetic_project, "P01.S01", spec)

    assert result.exit_code != 0
    assert expected in result.output
    assert not (synthetic_project / ".vault" / "exec" / _LEDGER).exists()


def test_logged_steps_map_back_through_the_shared_index(
    runner: CliRunner, synthetic_project: Path
) -> None:
    """The ADR's objection: a Step must still resolve to a real artifact."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.plan.status import ExecRecordIndex

    setup_test_plan(synthetic_project)
    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")
    _log(runner, synthetic_project, "P01.S02", "A:src/bar.py")

    reset_config()
    try:
        index = ExecRecordIndex.build(synthetic_project)
    finally:
        reset_config()

    stem = "2026-05-17-test-feature-ledger"
    assert index.record_for("test-feature", "S01") == stem
    assert index.record_for("test-feature", "S02") == stem
    # The fixture ships an unrelated corpus, so scope to this feature:
    # the ledger must not also be bucketed as unlinked.
    assert "test-feature" not in index.unlinked_by_feature
