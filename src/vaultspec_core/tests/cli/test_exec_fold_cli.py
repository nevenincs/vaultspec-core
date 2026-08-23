"""Integration tests for ``vault exec fold``, the body-v1 migration.

The fold is destructive, so these assert the safety properties first: it
refuses without ``--force``, a dry run writes nothing, and records are only
removed once the ledger carrying their content exists. Then the recovery
properties: Scope paths become rows, no operation is invented, and every
folded Step still resolves through the shared execution-record index.
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

_FOLDER = "2026-05-17-test-feature"
_PLAN_STEM = "2026-05-17-test-feature-plan"


def _write_record(project: Path, step_id: str, *scope: str) -> Path:
    path = project / ".vault" / "exec" / _FOLDER / f"{_FOLDER}-{step_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    scope_block = "\n".join(f"- `{s}`" for s in scope)
    lines = (
        "---",
        "tags:",
        "  - '#exec'",
        "  - '#test-feature'",
        "date: '2026-05-17'",
        "modified: '2026-05-17'",
        "body_schema: 'body-v1'",
        f"step_id: '{step_id}'",
        "related:",
        f"  - '[[{_PLAN_STEM}]]'",
        "---",
        "",
        "# did a thing",
        "",
        "## Scope",
        "",
        scope_block,
        "",
        "## Description",
        "",
        "Prose that no consumer reads.",
        "",
        "## Outcome",
        "",
        "More prose.",
        "",
        "## Notes",
        "",
        "Yet more prose.",
        "",
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _fold(runner: CliRunner, project: Path, *flags: str):
    return runner.invoke(
        app,
        [
            "--target",
            str(project),
            "vault",
            "exec",
            "fold",
            "--feature",
            "test-feature",
            *flags,
        ],
    )


def _ledger(project: Path) -> Path:
    return project / ".vault" / "exec" / _FOLDER / f"{_FOLDER}-ledger.md"


def test_refuses_without_force(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)
    record = _write_record(synthetic_project, "S01", "src/foo.py")

    result = _fold(runner, synthetic_project)

    assert result.exit_code != 0
    assert "Refusing to fold without --force" in result.output
    assert record.exists()
    assert not _ledger(synthetic_project).exists()


def test_dry_run_writes_nothing(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)
    record = _write_record(synthetic_project, "S01", "src/foo.py")

    result = _fold(runner, synthetic_project, "--dry-run", "--force")

    assert result.exit_code == 0, result.output
    assert record.exists()
    assert not _ledger(synthetic_project).exists()


def test_fold_recovers_scope_paths_and_removes_records(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)
    first = _write_record(synthetic_project, "S01", "src/foo.py", "tests/test_foo.py")
    second = _write_record(synthetic_project, "S02", "src/bar.py")

    result = _fold(runner, synthetic_project, "--force")

    assert result.exit_code == 0, result.output
    text = _ledger(synthetic_project).read_text(encoding="utf-8")
    assert "- `S01` `T` `src/foo.py`" in text
    assert "- `S01` `T` `tests/test_foo.py`" in text
    assert "- `S02` `T` `src/bar.py`" in text
    assert not first.exists()
    assert not second.exists()


def test_fold_never_invents_an_operation(
    runner: CliRunner, synthetic_project: Path
) -> None:
    setup_test_plan(synthetic_project)
    _write_record(synthetic_project, "S01", "src/foo.py")

    _fold(runner, synthetic_project, "--force")

    rows = [
        line
        for line in _ledger(synthetic_project).read_text(encoding="utf-8").splitlines()
        if line.startswith("- `S")
    ]
    assert rows
    for row in rows:
        assert "`T`" in row
        for invented in ("`A`", "`M`", "`D`", "`R`"):
            assert invented not in row


def test_prose_is_discarded(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)
    _write_record(synthetic_project, "S01", "src/foo.py")

    _fold(runner, synthetic_project, "--force")

    text = _ledger(synthetic_project).read_text(encoding="utf-8")
    assert "Prose that no consumer reads" not in text
    assert "More prose" not in text


def test_folded_steps_still_resolve_through_the_index(
    runner: CliRunner, synthetic_project: Path
) -> None:
    """A folded Step must not read as never executed."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.plan.status import ExecRecordIndex

    setup_test_plan(synthetic_project)
    _write_record(synthetic_project, "S01", "src/foo.py")
    _write_record(synthetic_project, "S02", "src/bar.py")

    _fold(runner, synthetic_project, "--force")

    reset_config()
    try:
        index = ExecRecordIndex.build(synthetic_project)
    finally:
        reset_config()

    stem = f"{_FOLDER}-ledger"
    assert index.record_for("test-feature", "S01") == stem
    assert index.record_for("test-feature", "S02") == stem


def test_step_without_scope_keeps_its_mapping(
    runner: CliRunner, synthetic_project: Path
) -> None:
    from vaultspec_core.config import reset_config
    from vaultspec_core.plan.status import ExecRecordIndex

    setup_test_plan(synthetic_project)
    path = _write_record(synthetic_project, "S01", "src/foo.py")
    # Strip the Scope section entirely.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("- `src/foo.py`", ""), encoding="utf-8")

    _fold(runner, synthetic_project, "--force")

    reset_config()
    try:
        index = ExecRecordIndex.build(synthetic_project)
    finally:
        reset_config()

    assert index.record_for("test-feature", "S01") == f"{_FOLDER}-ledger"


def test_fold_is_idempotent(runner: CliRunner, synthetic_project: Path) -> None:
    setup_test_plan(synthetic_project)
    _write_record(synthetic_project, "S01", "src/foo.py")

    _fold(runner, synthetic_project, "--force")
    first = _ledger(synthetic_project).read_text(encoding="utf-8")
    second_run = _fold(runner, synthetic_project, "--force")

    # Nothing left to fold; the ledger is untouched.
    assert _ledger(synthetic_project).read_text(encoding="utf-8") == first
    assert second_run.exit_code == 0, second_run.output


def test_unknown_feature_is_refused(runner: CliRunner, synthetic_project: Path) -> None:
    result = _fold(runner, synthetic_project, "--force", "--dry-run")

    assert result.exit_code != 0
    assert "no execution folder found" in result.output
