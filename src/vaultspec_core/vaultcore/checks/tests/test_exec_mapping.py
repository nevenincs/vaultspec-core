"""Tests for the ``exec-mapping`` vault health checker.

Exercises the back-mapping of an execution record's ``step_id`` to a live
Step in its parent plan against real on-disk documents: a valid mapping, a
retired Step id, a dangling id, a truly-missing parent plan, an archived
parent plan (the expected steady state, no finding), a legacy record without
``step_id`` (skipped), and an unparseable parent plan (degrades to a finding,
never a crash). No mocks, patches, or skips.
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
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _skeleton(root: Path) -> None:
    for sub in ("plan", "exec", "_archive"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)


def _plan_text(steps: tuple[str, ...], retired: tuple[str, ...] = ()) -> str:
    rows = "\n".join(
        f"- [ ] `{sid}` - do a thing; `src/{sid.lower()}.py`." for sid in steps
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
    stem: str = _PLAN_STEM,
    subdir: str = "plan",
    text: str | None = None,
) -> Path:
    path = root / ".vault" / subdir / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or _plan_text(steps, retired), encoding="utf-8")
    return path


def _write_exec(
    root: Path,
    *,
    step_id: str | None,
    plan_stem: str = _PLAN_STEM,
    stem: str = "2026-02-04-feat-S01",
    folder: str = "2026-02-04-feat",
) -> Path:
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


def _run(root: Path, *, feature: str | None = None):
    snapshot = VaultGraph(root).to_snapshot()
    return check_exec_mapping(root, snapshot=snapshot, feature=feature)


class TestExecMapping:
    def test_valid_mapping_is_clean(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"))
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        assert result.check_name == "exec-mapping"
        assert result.supports_fix is False
        assert result.diagnostics == []

    def test_dangling_step_id_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"))
        _write_exec(tmp_path, step_id="S09")

        result = _run(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "S09" in warnings[0].message
        assert "does not exist" in warnings[0].message
        assert result.fixed_count == 0

    def test_retired_step_id_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        # S02 was created then retired; the ledger records it, only S01 is live.
        _write_plan(tmp_path, ("S01",), retired=("S02",))
        _write_exec(tmp_path, step_id="S02")

        result = _run(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "retired Step S02" in warnings[0].message

    def test_missing_parent_plan_is_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        # No plan file written at all.
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "was not found" in warnings[0].message
        assert _PLAN_STEM in warnings[0].message

    def test_archived_parent_plan_produces_no_finding(self, tmp_path: Path) -> None:
        # Mandatory regression (#233): the parent plan lives under
        # .vault/_archive/plan/. The scanner hides _archive, so the plan is
        # absent from the snapshot; the checker must probe the archive on disk
        # and treat the archived parent as the expected steady state.
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"), subdir="_archive/plan")
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_legacy_record_without_step_id_is_skipped(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01", "S02"))
        _write_exec(tmp_path, step_id=None)

        result = _run(tmp_path)

        assert result.diagnostics == []

    def test_unparseable_plan_degrades_to_warning(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        # A plan file that parse_plan rejects: its frontmatter is missing the
        # required feature tag, so the plan frontmatter contract fails.
        broken = (
            "---\ntags:\n  - '#plan'\n"
            "date: '2026-02-04'\nmodified: '2026-02-04'\ntier: L1\nrelated: []\n---\n\n"
            "# plan\n\n## Steps\n\n- [ ] `S01` - a step; `src/x.py`.\n"
        )
        _write_plan(tmp_path, text=broken)
        _write_exec(tmp_path, step_id="S01")

        result = _run(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "could not be parsed" in warnings[0].message

    def test_feature_filter_scopes_findings(self, tmp_path: Path) -> None:
        _skeleton(tmp_path)
        _write_plan(tmp_path, ("S01",))
        _write_exec(tmp_path, step_id="S09")

        # A different feature filter excludes the record.
        result = _run(tmp_path, feature="other")

        assert result.diagnostics == []
