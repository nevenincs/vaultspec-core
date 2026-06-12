"""Tests for the orientation rollup and grounding-trace data core.

Covers the vault-orientation ADR's decisions D2, D4, D5, and D6 against a
small but real on-disk vault built in ``tmp_path``: rollup ordering by
``modified:`` recency, the date fallback, in-flight detection,
``limit`` / ``since_days`` windowing, step-to-record mapping including
the no-record and unlinked buckets, a feature-tag target spanning two
plans, and the unknown-target error.

The synthetic-corpus generator
(:func:`vaultspec_core.testing.synthetic.build_synthetic_vault`) does not
produce plan-step rows, ``step_id:`` execution-record linkage, or the
``modified:`` recency stamp this surface depends on, so these tests write
genuine vault documents directly. There are no mocks, patches, stubs, or
skips: every assertion reads structures computed from real files.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ..orientation import (
    TargetResolutionError,
    compute_rollup,
    compute_trace,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


# ---------------------------------------------------------------------------
# Real-vault builders
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plan(
    feature: str,
    *,
    date: str,
    modified: str | None,
    steps: list[tuple[str, bool]],
    related: list[str] | None = None,
) -> str:
    """Render an L2 plan document with one phase of explicit steps."""
    lines = ["---", "tags:", "  - '#plan'", f"  - '#{feature}'", f"date: '{date}'"]
    if modified is not None:
        lines.append(f"modified: '{modified}'")
    lines.append("tier: L2")
    if related:
        lines.append("related:")
        lines += [f"  - '[[{r}]]'" for r in related]
    else:
        lines.append("related: []")
    lines += [
        "---",
        "",
        f"# `{feature}` plan",
        "",
        f"{feature} plan body.",
        "",
        "## Phase `P01` - Build",
        "",
        "Phase intent.",
        "",
    ]
    for step_id, checked in steps:
        box = "x" if checked else " "
        lines.append(f"- [{box}] `P01.{step_id}` - do the work; `src/{step_id}.py`.")
    lines.append("")
    return "\n".join(lines)


def _exec(
    feature: str,
    *,
    date: str,
    modified: str | None,
    step_id: str | None,
    plan_stem: str,
) -> str:
    """Render an execution record, optionally carrying a ``step_id:``."""
    lines = ["---", "tags:", "  - '#exec'", f"  - '#{feature}'", f"date: '{date}'"]
    if modified is not None:
        lines.append(f"modified: '{modified}'")
    if step_id is not None:
        lines.append(f"step_id: '{step_id}'")
    lines += [
        "related:",
        f"  - '[[{plan_stem}]]'",
        "---",
        "",
        "Execution details.",
        "",
    ]
    return "\n".join(lines)


def _grounding(
    doc_type: str,
    feature: str,
    *,
    date: str,
    modified: str | None,
    related: list[str] | None = None,
) -> str:
    """Render a non-plan grounding document (adr, research, reference)."""
    lines = [
        "---",
        "tags:",
        f"  - '#{doc_type}'",
        f"  - '#{feature}'",
        f"date: '{date}'",
    ]
    if modified is not None:
        lines.append(f"modified: '{modified}'")
    if related:
        lines.append("related:")
        lines += [f"  - '[[{r}]]'" for r in related]
    else:
        lines.append("related: []")
    lines += ["---", "", f"# {feature} {doc_type}", "", "Body.", ""]
    return "\n".join(lines)


def _build_single_feature_vault(root: Path) -> dict[str, str]:
    """Build a vault with one feature: research, adr, a plan, and two execs.

    The plan ``S01`` is closed with a matching exec record, ``S02`` is
    closed with a record, ``S03`` is open with no record, and one extra
    exec record references the plan with no ``step_id:`` (the unlinked
    bucket). Returns the document stems for assertions.
    """
    vault = root / ".vault"
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)

    feature = "widget"
    plan_stem = f"2026-03-01-{feature}-plan"
    adr_stem = f"2026-02-20-{feature}-adr"
    research_stem = f"2026-02-10-{feature}-research"

    _write(
        vault / "research" / f"{research_stem}.md",
        _grounding("research", feature, date="2026-02-10", modified="2026-02-10"),
    )
    _write(
        vault / "adr" / f"{adr_stem}.md",
        _grounding(
            "adr",
            feature,
            date="2026-02-20",
            modified="2026-02-20",
            related=[research_stem],
        ),
    )
    _write(
        vault / "plan" / f"{plan_stem}.md",
        _plan(
            feature,
            date="2026-03-01",
            modified="2026-03-15",
            steps=[("S01", True), ("S02", True), ("S03", False)],
            related=[adr_stem, research_stem],
        ),
    )
    # Records for S01 and S02.
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-P01-S01.md",
        _exec(
            feature,
            date="2026-03-02",
            modified="2026-03-02",
            step_id="S01",
            plan_stem=plan_stem,
        ),
    )
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-P01-S02.md",
        _exec(
            feature,
            date="2026-03-10",
            modified="2026-03-10",
            step_id="S02",
            plan_stem=plan_stem,
        ),
    )
    # An exec record that references the plan but carries no step_id.
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-orphan.md",
        _exec(
            feature,
            date="2026-03-12",
            modified="2026-03-12",
            step_id=None,
            plan_stem=plan_stem,
        ),
    )

    return {
        "feature": feature,
        "plan": plan_stem,
        "adr": adr_stem,
        "research": research_stem,
        "exec_s01": f"2026-03-01-{feature}-P01-S01",
        "exec_s02": f"2026-03-01-{feature}-P01-S02",
        "exec_orphan": f"2026-03-01-{feature}-orphan",
    }


# ---------------------------------------------------------------------------
# Rollup: recency ordering and date fallback (D2 / D4 / D3b)
# ---------------------------------------------------------------------------


class TestRollupOrdering:
    """Active features and recent docs order by leniently-parsed recency."""

    def test_active_features_ordered_by_latest_activity(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        # 'older' feature: latest modified 2026-01-05.
        _write(
            vault / "research" / "2026-01-01-older-research.md",
            _grounding("research", "older", date="2026-01-01", modified="2026-01-05"),
        )
        # 'newer' feature: latest modified 2026-06-01.
        _write(
            vault / "research" / "2026-05-01-newer-research.md",
            _grounding("research", "newer", date="2026-05-01", modified="2026-06-01"),
        )

        rollup = compute_rollup(tmp_path)

        names = [f.name for f in rollup.active_features]
        assert names == ["newer", "older"]
        assert rollup.active_features[0].latest_activity == "2026-06-01"
        assert rollup.active_features[1].latest_activity == "2026-01-05"

    def test_recency_falls_back_to_date_when_modified_absent(
        self, tmp_path: Path
    ) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        # No modified stamp: recency must fall back to the date field.
        _write(
            vault / "research" / "2026-04-01-stampless-research.md",
            _grounding("research", "stampless", date="2026-04-01", modified=None),
        )

        rollup = compute_rollup(tmp_path)

        feature = next(f for f in rollup.active_features if f.name == "stampless")
        assert feature.latest_activity == "2026-04-01"

    def test_modified_overrides_date_for_ordering(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        # Created long ago, but modified recently: recency is the stamp.
        _write(
            vault / "adr" / "2025-01-01-revised-adr.md",
            _grounding("adr", "revised", date="2025-01-01", modified="2026-06-10"),
        )
        _write(
            vault / "adr" / "2026-02-01-fresh-adr.md",
            _grounding("adr", "fresh", date="2026-02-01", modified="2026-02-01"),
        )

        rollup = compute_rollup(tmp_path)

        names = [f.name for f in rollup.active_features]
        assert names == ["revised", "fresh"]


# ---------------------------------------------------------------------------
# Rollup: in-flight detection and windowing (D2 / D4 / D6)
# ---------------------------------------------------------------------------


class TestRollupInFlight:
    """Plans with open steps are detected and counted; closed plans drop out."""

    def test_in_flight_plan_counts(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        rollup = compute_rollup(tmp_path)

        in_flight = rollup.plans_in_flight
        assert len(in_flight) == 1
        plan = in_flight[0]
        assert plan.stem == stems["plan"]
        assert plan.total_steps == 3
        assert plan.closed_steps == 2
        assert plan.open_steps == 1
        assert plan.completion_percent == pytest.approx(66.7)

    def test_fully_closed_plan_is_not_in_flight(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        _write(
            vault / "plan" / "2026-03-01-done-plan.md",
            _plan(
                "done",
                date="2026-03-01",
                modified="2026-03-01",
                steps=[("S01", True), ("S02", True)],
            ),
        )

        rollup = compute_rollup(tmp_path)

        assert rollup.plans_in_flight == []

    def test_in_flight_ordered_most_recently_modified_first(
        self, tmp_path: Path
    ) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        _write(
            vault / "plan" / "2026-01-01-stale-plan.md",
            _plan(
                "stale",
                date="2026-01-01",
                modified="2026-01-02",
                steps=[("S01", False)],
            ),
        )
        _write(
            vault / "plan" / "2026-01-01-active-plan.md",
            _plan(
                "active",
                date="2026-01-01",
                modified="2026-06-01",
                steps=[("S01", False)],
            ),
        )

        rollup = compute_rollup(tmp_path)

        stems = [p.stem for p in rollup.plans_in_flight]
        assert stems == ["2026-01-01-active-plan", "2026-01-01-stale-plan"]


class TestRollupRecencyWindow:
    """The limit default and the since_days window both shape recent docs."""

    def test_limit_caps_recent_documents(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        for day in range(1, 13):
            _write(
                vault / "research" / f"2026-01-{day:02d}-doc{day:02d}-research.md",
                _grounding(
                    "research",
                    f"feat{day:02d}",
                    date=f"2026-01-{day:02d}",
                    modified=f"2026-01-{day:02d}",
                ),
            )

        rollup = compute_rollup(tmp_path, limit=5)

        total = sum(len(docs) for docs in rollup.recent_documents.values())
        assert total == 5
        # The five kept must be the five most recent (days 12..8).
        stems = {d.stem for docs in rollup.recent_documents.values() for d in docs}
        assert stems == {
            "2026-01-12-doc12-research",
            "2026-01-11-doc11-research",
            "2026-01-10-doc10-research",
            "2026-01-09-doc09-research",
            "2026-01-08-doc08-research",
        }

    def test_since_days_window_filters_by_age(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        today = datetime.date(2026, 6, 15)
        # Inside the 10-day window.
        _write(
            vault / "adr" / "2026-06-10-recent-adr.md",
            _grounding("adr", "recent", date="2026-06-10", modified="2026-06-10"),
        )
        # Outside the window.
        _write(
            vault / "adr" / "2026-01-01-ancient-adr.md",
            _grounding("adr", "ancient", date="2026-01-01", modified="2026-01-01"),
        )

        rollup = compute_rollup(tmp_path, since_days=10, today=today)

        stems = {d.stem for docs in rollup.recent_documents.values() for d in docs}
        assert "2026-06-10-recent-adr" in stems
        assert "2026-01-01-ancient-adr" not in stems
        assert rollup.since_days == 10

    def test_recent_documents_grouped_by_type(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        rollup = compute_rollup(tmp_path)

        # Every grouped doc's reported type matches its group key.
        for doc_type, docs in rollup.recent_documents.items():
            assert all(d.doc_type == doc_type for d in docs)
        assert "plan" in rollup.recent_documents
        assert stems["plan"] in {d.stem for d in rollup.recent_documents["plan"]}


# ---------------------------------------------------------------------------
# Grounding trace: step-to-record mapping (D5)
# ---------------------------------------------------------------------------


class TestTraceStepMapping:
    """Each step maps to its record stem, None, or the unlinked bucket."""

    def test_step_to_record_mapping(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        trace = compute_trace(tmp_path, stems["plan"])

        assert trace.kind == "plan"
        assert len(trace.plans) == 1
        plan = trace.plans[0]
        assert plan.error is None

        by_step = {s.canonical_id: s for s in plan.steps}
        assert by_step["S01"].record_stem == stems["exec_s01"]
        assert by_step["S01"].checked is True
        assert by_step["S02"].record_stem == stems["exec_s02"]
        # Open step with no record maps to None (the explicit no-record state).
        assert by_step["S03"].checked is False
        assert by_step["S03"].record_stem is None

    def test_step_display_paths_are_tier_conditional(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        trace = compute_trace(tmp_path, stems["plan"])

        plan = trace.plans[0]
        paths = {s.canonical_id: s.display_path for s in plan.steps}
        # An L2 plan renders display paths as P##.S##.
        assert paths["S01"] == "P01.S01"

    def test_unlinked_records_surfaced(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        trace = compute_trace(tmp_path, stems["plan"])

        plan = trace.plans[0]
        # The step-less exec record that links the plan lands in the bucket.
        assert stems["exec_orphan"] in plan.unlinked_records
        # The step-mapped records do not.
        assert stems["exec_s01"] not in plan.unlinked_records
        assert stems["exec_s02"] not in plan.unlinked_records

    def test_grounding_documents_grouped_by_type(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        trace = compute_trace(tmp_path, stems["plan"])

        grounding = trace.plans[0].grounding
        assert grounding.get("adr") == [stems["adr"]]
        assert grounding.get("research") == [stems["research"]]
        # Exec records are never grounding context.
        assert "exec" not in grounding


# ---------------------------------------------------------------------------
# Grounding trace: target resolution (D5)
# ---------------------------------------------------------------------------


class TestTraceTargetResolution:
    """Plan stem, plan path, and feature-tag targets resolve correctly."""

    def test_plan_path_target(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)
        plan_path = tmp_path / ".vault" / "plan" / f"{stems['plan']}.md"

        trace = compute_trace(tmp_path, str(plan_path))

        assert trace.kind == "plan"
        assert [p.stem for p in trace.plans] == [stems["plan"]]

    def test_feature_tag_target_spans_two_plans(self, tmp_path: Path) -> None:
        vault = tmp_path / ".vault"
        (tmp_path / ".vaultspec").mkdir(parents=True, exist_ok=True)
        feature = "multi"
        _write(
            vault / "plan" / "2026-01-01-multi-alpha-plan.md",
            _plan(
                feature,
                date="2026-01-01",
                modified="2026-01-01",
                steps=[("S01", False)],
            ),
        )
        _write(
            vault / "plan" / "2026-02-01-multi-beta-plan.md",
            _plan(
                feature,
                date="2026-02-01",
                modified="2026-02-01",
                steps=[("S01", True)],
            ),
        )

        trace = compute_trace(tmp_path, f"#{feature}")

        assert trace.kind == "feature"
        stems = [p.stem for p in trace.plans]
        assert stems == ["2026-01-01-multi-alpha-plan", "2026-02-01-multi-beta-plan"]

    def test_feature_tag_without_hash_resolves(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)

        trace = compute_trace(tmp_path, stems["feature"])

        assert trace.kind == "feature"
        assert [p.stem for p in trace.plans] == [stems["plan"]]

    def test_unknown_target_raises_with_near_matches(self, tmp_path: Path) -> None:
        _build_single_feature_vault(tmp_path)

        with pytest.raises(TargetResolutionError) as exc_info:
            compute_trace(tmp_path, "widg")

        # 'widg' is a substring of the 'widget' feature, so it is suggested.
        assert any("widget" in match for match in exc_info.value.near_matches)

    def test_wholly_unknown_target_raises(self, tmp_path: Path) -> None:
        _build_single_feature_vault(tmp_path)

        with pytest.raises(TargetResolutionError):
            compute_trace(tmp_path, "no-such-thing-at-all")

    def test_phase_summary_grouped_separately(self, tmp_path: Path) -> None:
        stems = _build_single_feature_vault(tmp_path)
        feature = "widget"
        summary_stem = f"2026-03-01-{feature}-P01-summary"
        _write(
            tmp_path
            / ".vault"
            / "exec"
            / f"2026-03-01-{feature}"
            / f"{summary_stem}.md",
            _exec(
                feature,
                date="2026-03-14",
                modified="2026-03-14",
                step_id=None,
                plan_stem=stems["plan"],
            ),
        )

        trace = compute_trace(tmp_path, stems["plan"])

        plan = trace.plans[0]
        # A -summary document referencing the plan is a summary by design,
        # not an unlinked anomaly.
        assert summary_stem in plan.summaries
        assert summary_stem not in plan.unlinked_records
        assert stems["exec_orphan"] in plan.unlinked_records
