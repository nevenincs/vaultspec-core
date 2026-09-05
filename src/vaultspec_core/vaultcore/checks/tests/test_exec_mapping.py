"""Tests for the ``exec-mapping`` vault health checker.

Exercises the pairing of ledger rows with plan Steps against real on-disk
documents, and pins the severity of every finding: a check that never
blocks is not a guard, so the severities are asserted here rather than
described in prose. No mocks, patches, or skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from .._base import Severity
from ..exec_mapping import check_exec_mapping

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_PLAN_STEM = "2026-02-04-feat-plan"


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _skeleton(root: Path) -> None:
    for sub in ("plan", "exec", "_archive"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)


def _plan_text(
    steps: tuple[str, ...],
    retired: tuple[str, ...] = (),
    checked: tuple[str, ...] = (),
) -> str:
    rows = "\n".join(
        f"- [{'x' if sid in checked else ' '}] `{sid}` - do a thing; "
        f"`src/{sid.lower()}.py`."
        for sid in steps
    )
    ledger = f"\n<!-- RETIRED: {', '.join(retired)} -->\n" if retired else ""
    return (
        "---\ntags:\n  - '#plan'\n  - '#feat'\n"
        "date: '2026-02-04'\nmodified: '2026-02-04'\ntier: L1\nrelated: []\n---\n\n"
        "# `feat` plan\n\n## Description\n\nProse.\n\n## Steps\n\n"
        f"{rows}\n{ledger}\n## Parallelization\n\nProse.\n\n"
        "## Verification\n\nProse.\n"
    )


def _write_plan(
    root: Path,
    steps: tuple[str, ...] = ("S01", "S02"),
    *,
    retired: tuple[str, ...] = (),
    checked: tuple[str, ...] = (),
    stem: str = _PLAN_STEM,
    subdir: str = "plan",
    text: str | None = None,
) -> Path:
    path = root / ".vault" / subdir / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or _plan_text(steps, retired, checked), encoding="utf-8")
    return path


def _write_exec(
    root: Path,
    *,
    step_id: str | None,
    plan_stem: str = _PLAN_STEM,
    stem: str = "2026-02-04-feat-S01",
    folder: str = "2026-02-04-feat",
) -> Path:
    """Write a legacy per-Step record, optionally carrying ``step_id:``."""
    step_line = f"step_id: '{step_id}'\n" if step_id is not None else ""
    path = root / ".vault" / "exec" / folder / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntags:\n  - '#exec'\n  - '#feat'\n"
        f"date: '2026-02-04'\nmodified: '2026-02-04'\n{step_line}"
        f"related:\n  - '[[{plan_stem}]]'\n---\n\n"
        "# Step record\n\n## Description\n\nDone.\n",
        encoding="utf-8",
    )
    return path


def _write_ledger(
    root: Path,
    *,
    rows: str,
    plan_stem: str = _PLAN_STEM,
    stem: str = "2026-02-04-feat-ledger",
    folder: str = "2026-02-04-feat",
) -> Path:
    """Write a ledger naming its Steps in ``## Changes`` rows."""
    path = root / ".vault" / "exec" / folder / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---",
        "tags:",
        "  - '#exec'",
        "  - '#feat'",
        "date: '2026-02-04'",
        "modified: '2026-02-04'",
        "related:",
        f"  - '[[{plan_stem}]]'",
        "---",
        "",
        "# `feat` ledger",
        "",
        "## Changes",
        "",
    )
    path.write_text("\n".join((*frontmatter, rows)), encoding="utf-8")
    return path


def _run(root: Path, *, feature: str | None = None):
    snapshot = VaultGraph(root).to_snapshot()
    return check_exec_mapping(root, snapshot=snapshot, feature=feature)


def _by_severity(result, severity: Severity):
    return [d for d in result.diagnostics if d.severity == severity]


class TestPerStepRecordIsAnError:
    """A non-ledger record carrying ``step_id:`` is refused, not tolerated."""

    def test_record_with_step_id_is_error_naming_the_fold(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        errors = _by_severity(result, Severity.ERROR)
        assert len(errors) == 1
        assert "vault exec log" in errors[0].message
        assert "vault exec fold --feature feat --force" in errors[0].fix_description
        assert result.check_name == "exec-mapping"
        assert result.supports_fix is False

    def test_record_still_counts_as_coverage(self, tmp_path: Path) -> None:
        """The record's Step is not also reported as a missing row."""
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        assert [d.severity for d in result.diagnostics] == [Severity.ERROR]

    def test_legacy_record_without_step_id_is_skipped(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"))
        _write_exec(tmp_path, step_id=None)

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_feature_filter_scopes_findings(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",), checked=("S01",))
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path, feature="other")

        assert result.diagnostics == []


class TestLedgerRows:
    """Each ledger row is classified against its plan's Step sets."""

    def test_rows_for_closed_live_steps_are_clean(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01", "S02"))
        _write_ledger(
            tmp_path,
            rows="- `S01` `M` `src/s01.py`\n- `S02` `A` `src/s02.py`\n",
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_row_for_open_step_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        _write_ledger(
            tmp_path,
            rows="- `S01` `M` `src/s01.py`\n- `S02` `A` `src/s02.py`\n",
        )

        result = _run(tmp_path)

        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1
        assert "S02" in warnings[0].message and "still open" in warnings[0].message
        assert _by_severity(result, Severity.ERROR) == []

    def test_row_for_retired_step_is_clean(self, tmp_path: Path) -> None:
        """Ledger rows are history: the Step ran before it was retired."""
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",), retired=("S02",), checked=("S01",))
        _write_ledger(
            tmp_path,
            rows="- `S01` `M` `src/s01.py`\n- `S02` `M` `src/s02.py`\n",
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_row_for_unknown_step_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        _write_ledger(
            tmp_path,
            rows="- `S01` `M` `src/s01.py`\n- `S99` `M` `src/gone.py`\n",
        )

        result = _run(tmp_path)

        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1
        assert "S99" in warnings[0].message and "does not exist" in warnings[0].message

    def test_verify_and_by_rows_count_as_coverage(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",), checked=("S01",))
        _write_ledger(
            tmp_path,
            rows="- `S01` `verify:` `pytest` -> `pass`\n- `S01` `by:` `worker`\n",
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_notes_prose_never_registers_a_step(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        path = _write_ledger(tmp_path, rows="- `S01` `M` `src/s01.py`\n")
        path.write_text(
            path.read_text(encoding="utf-8") + "\n## Notes\n\n- `S02` was skipped.\n",
            encoding="utf-8",
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_template_hint_examples_never_register_a_step(self, tmp_path: Path) -> None:
        """Rows inside an HTML comment are guidance, not evidence."""
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01",))
        _write_ledger(
            tmp_path,
            rows=(
                "<!-- example:\n  - `S02` `M` `src/example.py`\n-->\n"
                "- `S01` `M` `src/s01.py`\n"
            ),
        )

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_ledger_naming_no_step_is_skipped_not_flagged(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",))
        _write_ledger(tmp_path, rows="- `M` `src/s01.py`\n")

        result = _run(tmp_path)

        assert result.diagnostics == []


class TestClosedStepsWithoutRows:
    """A closed Step needs a row; how loudly depends on whether a ledger exists."""

    def test_missing_rows_are_warning_without_a_ledger(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01", "S02"))

        result = _run(tmp_path)

        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1
        assert "S01, S02" in warnings[0].message
        assert "no logged ledger yet" in warnings[0].message
        assert warnings[0].path.name == f"{_PLAN_STEM}.md"
        assert _by_severity(result, Severity.ERROR) == []

    def test_missing_rows_are_error_when_the_ledger_exists(
        self, tmp_path: Path
    ) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01", "S02"))
        _write_ledger(tmp_path, rows="- `S01` `M` `src/s01.py`\n")

        result = _run(tmp_path)

        errors = _by_severity(result, Severity.ERROR)
        assert len(errors) == 1
        assert "S02" in errors[0].message and "S01" not in errors[0].message
        assert "closed without evidence" in errors[0].message
        assert "vault exec log" in errors[0].fix_description

    def test_missing_rows_stay_warning_under_a_folded_only_ledger(
        self, tmp_path: Path
    ) -> None:
        """A ledger the fold wrote (all ``T`` rows) is history, not logging."""
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01", "S02"))
        _write_ledger(tmp_path, rows="- `S01` `T` `src/s01.py`\n")

        result = _run(tmp_path)

        assert _by_severity(result, Severity.ERROR) == []
        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1 and "S02" in warnings[0].message

    def test_a_verify_row_alone_makes_the_ledger_native(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), checked=("S01", "S02"))
        _write_ledger(
            tmp_path,
            rows="- `S01` `T` `src/s01.py`\n- `S01` `verify:` `pytest` -> `pass`\n",
        )

        result = _run(tmp_path)

        assert len(_by_severity(result, Severity.ERROR)) == 1

    def test_open_steps_need_no_rows(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"))

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_feature_filter_scopes_plan_findings(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",), checked=("S01",))

        result = _run(tmp_path, feature="other")

        assert result.diagnostics == []


class TestParentPlanResolution:
    def test_missing_parent_plan_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_ledger(tmp_path, rows="- `S01` `M` `src/s01.py`\n")

        result = _run(tmp_path)

        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1
        assert "was not found" in warnings[0].message
        assert _PLAN_STEM in warnings[0].message

    def test_archived_parent_plan_produces_no_finding(self, tmp_path: Path) -> None:
        # Regression (#233): the parent plan lives under .vault/_archive/plan/.
        # The scanner hides _archive, so the plan is absent from the snapshot;
        # the checker must probe the archive on disk and treat the archived
        # parent as the expected steady state.
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), subdir="_archive/plan")
        _write_ledger(tmp_path, rows="- `S01` `M` `src/s01.py`\n")

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_unparseable_plan_degrades_to_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        broken = (
            "---\ntags:\n  - '#plan'\n"
            "date: '2026-02-04'\nmodified: '2026-02-04'\ntier: L1\nrelated: []\n---\n\n"
            "# plan\n\n## Steps\n\n- [ ] `S01` - a step; `src/x.py`.\n"
        )
        _write_plan(tmp_path, text=broken)
        _write_ledger(tmp_path, rows="- `S01` `M` `src/s01.py`\n")

        result = _run(tmp_path)

        warnings = _by_severity(result, Severity.WARNING)
        assert len(warnings) == 1
        assert "could not be parsed" in warnings[0].message
