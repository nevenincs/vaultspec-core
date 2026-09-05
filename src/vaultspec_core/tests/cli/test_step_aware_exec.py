"""Integration tests for the one-artifact rule on ``vault add exec``.

Execution has one artifact, the plan's ledger, and one writer,
``vault exec log``. These tests hold the scaffolder to that: ``vault add
exec`` refuses before touching disk, the removed Step-aware flags are gone
from its surface, and plan status pairs closed Steps with ledger rows rather
than per-Step records.

``setup_test_plan`` is shared with the ledger, fold, and merge suites.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

from vaultspec_core.cli import app

pytestmark = [pytest.mark.integration]

_PLAN_STEM = "2026-05-17-test-feature-plan"


def setup_test_plan(project_dir: Path) -> Path:
    """Write a clean L2 test plan (S01, S02 closed; S03 open) and its ADR."""
    adr_dir = project_dir / ".vault" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr_file = adr_dir / "2026-05-17-test-feature-adr.md"
    adr_file.write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#test-feature'\n"
        "date: '2026-05-17'\n"
        "---\n"
        "\n"
        "# `test-feature` adr: Architectural Decision\n",
        encoding="utf-8",
    )

    plan_dir = project_dir / ".vault" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / f"{_PLAN_STEM}.md"
    plan_file.write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#test-feature'\n"
        "date: '2026-05-17'\n"
        "tier: L2\n"
        "---\n"
        "\n"
        "# `test-feature` plan\n"
        "\n"
        "### Phase `P01` - Test Phase\n"
        "- [x] `P01.S01` - First step; `src/foo.py`.\n"
        "- [x] `P01.S02` - Second step; `src/bar.py`.\n"
        "- [ ] `P01.S03` - Third step; `src/baz.py`.\n",
        encoding="utf-8",
    )
    return plan_file


def _add_exec(runner: CliRunner, project: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "--target",
            str(project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            *extra,
        ],
    )


def _log(runner: CliRunner, project: Path, step: str, *extra: str):
    return runner.invoke(
        app,
        [
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
            *extra,
        ],
    )


class TestAddExecRefuses:
    """``vault add exec`` is not a scaffold path any more."""

    def test_refuses_with_the_ledger_message(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)

        result = _add_exec(runner, synthetic_project)

        assert result.exit_code == 1
        assert "execution is logged with `vault exec log`" in result.output

    def test_refuses_before_touching_disk(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)
        exec_root = synthetic_project / ".vault" / "exec"
        before = sorted(exec_root.rglob("*.md")) if exec_root.exists() else []

        _add_exec(runner, synthetic_project, "--title", "Legacy Record")

        after = sorted(exec_root.rglob("*.md")) if exec_root.exists() else []
        assert after == before
        assert not list(exec_root.glob("*-test-feature-exec.md"))

    def test_refuses_even_with_json(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)

        result = _add_exec(runner, synthetic_project, "--json")

        assert result.exit_code == 1

    @pytest.mark.parametrize(
        "flag",
        [("--step", "P01.S01"), ("--all-steps",), ("--summary",), ("--phase", "P01")],
    )
    def test_step_aware_flags_are_gone(
        self, runner: CliRunner, synthetic_project: Path, flag: tuple[str, ...]
    ) -> None:
        """The removed options are unknown to the parser, not merely ignored."""
        setup_test_plan(synthetic_project)

        result = _add_exec(runner, synthetic_project, *flag)

        assert result.exit_code != 0
        assert "No such option" in result.output

    def test_other_types_still_scaffold(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "audit",
                "--feature",
                "test-feature",
            ],
        )

        assert result.exit_code == 0, result.output
        assert list((synthetic_project / ".vault" / "audit").glob("*test-feature*"))


class TestStatusPairsStepsWithLedgerRows:
    """Plan status reports ``exec-missing`` from ledger rows."""

    def test_exec_missing_clears_as_steps_are_logged(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        plan_path = str(setup_test_plan(synthetic_project))
        status_args = ["--target", str(synthetic_project), "vault", "plan", "status"]

        result = runner.invoke(app, [*status_args, plan_path])
        assert result.exit_code == 0
        assert "! exec-missing" in result.output
        assert "S01" in result.output and "S02" in result.output

        result_json = runner.invoke(app, [*status_args, plan_path, "--json"])
        assert result_json.exit_code == 0
        data = json.loads(result_json.output)
        assert set(data["data"]["exec_missing_ids"]) == {"S01", "S02"}

        logged = _log(runner, synthetic_project, "P01.S01", "--row", "M:src/foo.py")
        assert logged.exit_code == 0, logged.output

        result2 = runner.invoke(app, [*status_args, plan_path])
        assert result2.exit_code == 0
        assert "S01" not in result2.output
        assert "S02" in result2.output

    def test_trace_shows_ledger_rows_and_verify_state(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)
        _log(
            runner,
            synthetic_project,
            "P01.S01",
            "--row",
            "M:src/foo.py",
            "--row",
            "A:tests/test_foo.py",
            "--verify",
            "pytest -q=pass",
        )
        _log(runner, synthetic_project, "P01.S02", "--row", "M:src/bar.py")

        result = runner.invoke(
            app, ["--target", str(synthetic_project), "status", _PLAN_STEM]
        )

        assert result.exit_code == 0, result.output
        lines = {
            key: next(
                line
                for line in result.output.splitlines()
                if key in line and "[" in line
            )
            for key in ("P01.S01", "P01.S02", "P01.S03")
        }
        assert "ledger 2 rows" in lines["P01.S01"]
        assert "verify:pass" in lines["P01.S01"]
        assert "ledger 1 row" in lines["P01.S02"]
        assert "verify:" not in lines["P01.S02"]
        assert "no rows" in lines["P01.S03"]
        assert "no record" not in result.output
        assert "summaries" not in result.output

    def test_trace_json_carries_rows_and_verify(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        setup_test_plan(synthetic_project)
        _log(
            runner,
            synthetic_project,
            "P01.S01",
            "--row",
            "M:src/foo.py",
            "--verify",
            "pytest=fail",
        )

        result = runner.invoke(
            app, ["--target", str(synthetic_project), "status", _PLAN_STEM, "--json"]
        )

        assert result.exit_code == 0, result.output
        plan = json.loads(result.output)["data"]["plans"][0]
        by_step = {s["canonical_id"]: s for s in plan["steps"]}
        assert by_step["S01"]["rows"] == 1
        assert by_step["S01"]["verify"] == "fail"
        assert by_step["S03"]["rows"] is None
        assert "summaries" not in plan
