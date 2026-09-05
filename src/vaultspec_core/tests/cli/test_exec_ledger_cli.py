"""Integration tests for ``vault exec log``, the ledger writer.

Covers first-use creation, append-only accumulation across Steps, idempotent
re-logging, rename and delete rows, the ``verify:``, ``by:``, and
``## Notes`` writers, malformed-spec refusal, and the round-trip that
matters: a logged Step must map back through the shared execution-record
index.
"""

from __future__ import annotations

import json
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


def _log(
    runner: CliRunner,
    project: Path,
    step: str,
    *rows: str,
    bare: tuple[str, ...] = (),
    **flags: str,
):
    """Invoke ``vault exec log``; *bare* carries value-less flags."""
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
    for name, value in flags.items():
        args += [f"--{name.replace('_', '-')}", value]
    args += list(bare)
    return runner.invoke(app, args)


def _ledger_path(project: Path) -> Path:
    return project / ".vault" / "exec" / _LEDGER


def _ledger_text(project: Path) -> str:
    return _ledger_path(project).read_text(encoding="utf-8")


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
    assert "\n## Notes\n" not in text


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
    assert text.count("## Changes") == 1


def test_relogging_the_same_row_is_idempotent(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)

    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")
    before = _ledger_text(synthetic_project)
    result = _log(
        runner, synthetic_project, "P01.S01", "M:src/foo.py", bare=("--json",)
    )

    assert _ledger_text(synthetic_project) == before
    payload = json.loads(result.output)
    assert payload["data"]["changed"] is False


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


def test_verify_and_by_become_rows(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)

    result = _log(
        runner,
        synthetic_project,
        "P01.S01",
        "M:src/foo.py",
        verify="uv run pytest -q=pass",
        by="vaultspec-high-executor",
    )

    assert result.exit_code == 0, result.output
    text = _ledger_text(synthetic_project)
    assert "- `S01` `verify:` `uv run pytest -q` -> `pass`" in text
    assert "- `S01` `by:` `vaultspec-high-executor`" in text
    # Both rows sit inside ## Changes, so they count as coverage.
    changes = text.split("## Changes", 1)[1]
    assert "`verify:`" in changes and "`by:`" in changes


def test_note_creates_the_notes_section_on_first_use(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)

    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py")
    assert "\n## Notes\n" not in _ledger_text(synthetic_project)

    result = _log(
        runner,
        synthetic_project,
        "P01.S02",
        "M:src/bar.py",
        note="left a scaffold in src/bar.py",
    )

    assert result.exit_code == 0, result.output
    text = _ledger_text(synthetic_project)
    assert text.count("\n## Notes\n") == 1
    assert "- `S02` left a scaffold in src/bar.py" in text
    # Notes follow Changes and never register a Step as covered.
    assert text.index("\n## Notes\n") > text.index("- `S02` `M` `src/bar.py`")


def test_note_only_log_still_covers_nothing(
    runner: CliRunner, synthetic_project: Path
) -> None:
    """A note without rows leaves the Step unmapped: notes are not evidence."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.plan.status import ExecRecordIndex

    setup_test_plan(synthetic_project)
    _log(runner, synthetic_project, "P01.S01", note="skipped: blocked on S00")

    reset_config()
    try:
        index = ExecRecordIndex.build(synthetic_project)
    finally:
        reset_config()
    assert index.record_for("test-feature", "S01") is None


def test_dry_run_writes_nothing(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)

    result = _log(
        runner, synthetic_project, "P01.S01", "M:src/foo.py", bare=("--dry-run",)
    )

    assert result.exit_code == 0, result.output
    assert "Would log" in result.output
    assert not _ledger_path(synthetic_project).exists()


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
    assert not _ledger_path(synthetic_project).exists()


@pytest.mark.parametrize("spec", ["pytest", "pytest=maybe", "=pass"])
def test_malformed_verify_is_refused(
    runner: CliRunner, synthetic_project: Path, spec: str
) -> None:
    setup_test_plan(synthetic_project)

    result = _log(runner, synthetic_project, "P01.S01", "M:src/foo.py", verify=spec)

    assert result.exit_code != 0
    assert "invalid --verify" in result.output
    assert not _ledger_path(synthetic_project).exists()


def test_unknown_step_is_refused(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)

    result = _log(runner, synthetic_project, "S99", "M:src/foo.py")

    assert result.exit_code != 0
    assert not _ledger_path(synthetic_project).exists()


def test_logged_steps_map_back_through_the_shared_index(
    runner: CliRunner, synthetic_project: Path
) -> None:
    """The ADR's objection: a Step must still resolve to a real artifact."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.plan.status import ExecRecordIndex

    setup_test_plan(synthetic_project)
    _log(runner, synthetic_project, "P01.S01", "M:src/foo.py", verify="pytest=pass")
    _log(runner, synthetic_project, "P01.S02", "A:src/bar.py")

    reset_config()
    try:
        index = ExecRecordIndex.build(synthetic_project)
    finally:
        reset_config()

    stem = "2026-05-17-test-feature-ledger"
    assert index.record_for("test-feature", "S01") == stem
    assert index.record_for("test-feature", "S02") == stem
    evidence = index.evidence_for("test-feature", "S01")
    assert evidence is not None
    assert (evidence.rows, evidence.verify) == (1, "pass")
    # The fixture ships an unrelated corpus, so scope to this feature:
    # the ledger must not also be bucketed as unlinked.
    assert "test-feature" not in index.unlinked_by_feature


def test_ledger_passes_the_vault_checks(
    runner: CliRunner, synthetic_project: Path
) -> None:
    """A verb-written ledger is clean under `check all`, notes included."""
    setup_test_plan(synthetic_project)
    _log(
        runner,
        synthetic_project,
        "P01.S01",
        "M:src/foo.py",
        verify="pytest=pass",
        note="nothing skipped",
    )
    _log(runner, synthetic_project, "P01.S02", "M:src/bar.py")

    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "check",
            "exec-mapping",
            "--feature",
            "test-feature",
        ],
    )

    assert result.exit_code == 0, result.output
    stamp = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "check",
            "modified-stamp",
            "--feature",
            "test-feature",
        ],
    )
    assert stamp.exit_code == 0, stamp.output
