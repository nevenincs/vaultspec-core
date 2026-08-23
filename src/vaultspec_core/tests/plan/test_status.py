"""Tests for plan-status snapshot collection and JSON emission."""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.status import collect_status, status_to_json_dict
from vaultspec_core.tests.plan._factories import make_clean_plan


@pytest.mark.parametrize(
    ("tier", "waves", "phases", "steps", "expected_step_count"),
    [
        ("L1", 0, 0, 5, 5),
        ("L2", 0, 2, 3, 6),
        ("L3", 2, 2, 2, 8),
        ("L4", 1, 3, 2, 6),
    ],
)
def test_status_step_count_matches_factory(
    tier: str,
    waves: int,
    phases: int,
    steps: int,
    expected_step_count: int,
) -> None:
    """The snapshot's ``step_count`` matches the factory's emitted Step count."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=waves, phases=phases, steps=steps)
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.step_count == expected_step_count


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_status_completion_starts_at_zero_for_open_plans(tier: str) -> None:
    """A factory plan starts with every Step open; completion must be 0%."""
    rng = random.Random(1)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.steps_completed == 0
    assert status.completion_percent == 0.0


def test_status_completion_with_some_closed_steps() -> None:
    """Closing half the Steps yields a 50% completion percentage."""
    rng = random.Random(2)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    for index, step in enumerate(spec.steps):
        step.checked = index % 2 == 0
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.step_count == 4
    assert status.steps_completed == 2
    assert status.completion_percent == 50.0


def test_status_legacy_default_flag_propagates() -> None:
    """When the parser applies the L2 default, the snapshot reflects it."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#legacy'\n"
        "date: '2026-05-05'\n"
        "---\n"
        "\n"
        "# `legacy` plan\n"
        "\n"
        "Legacy plan without tier field.\n"
    )
    plan = parse_plan(body)

    status = collect_status(plan)

    assert status.tier is Tier.L2
    assert status.legacy_tier_default is True


def test_status_to_json_dict_round_trips_through_json_module() -> None:
    """The snapshot dict survives a real ``json.dumps`` / ``json.loads``."""
    rng = random.Random(3)
    spec = make_clean_plan("L4", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    status = collect_status(plan)
    payload = status_to_json_dict(status)

    serialised = json.dumps(payload)
    restored = json.loads(serialised)
    assert restored == payload
    assert restored["tier"] == "L4"
    assert restored["has_epic_intent"] is True


def test_enrichment_partial_l3_counts_completed_containers() -> None:
    """Closing the first Wave's Steps yields one completed Wave, two Phases,
    and a cursor on the first open Step of the next Wave."""
    rng = random.Random(10)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    # W01 owns S01-S04 (P01: S01,S02 / P02: S03,S04); close exactly those.
    for step in spec.steps[:4]:
        step.checked = True
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.waves_completed == 1
    assert status.phases_completed == 2
    assert status.next_open_step == "W02.P03.S05"


def test_enrichment_complete_plan_has_no_cursor() -> None:
    """A fully-checked plan reports every container complete and no cursor."""
    rng = random.Random(11)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    for step in spec.steps:
        step.checked = True
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.waves_completed == 2
    assert status.phases_completed == 4
    assert status.next_open_step is None


def test_enrichment_l2_has_phases_but_no_completed_waves() -> None:
    """An L2 plan never reports completed Waves; Phase completion still counts."""
    rng = random.Random(12)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    for step in spec.steps[:2]:  # close the first Phase only
        step.checked = True
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.wave_count == 0
    assert status.waves_completed == 0
    assert status.phases_completed == 1
    assert status.next_open_step == "P02.S03"


def test_enrichment_l1_cursor_is_first_open_flat_step() -> None:
    """An L1 plan has no containers; the cursor is the first open flat Step."""
    rng = random.Random(13)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    spec.steps[0].checked = True
    plan = parse_plan(spec.render())

    status = collect_status(plan)

    assert status.waves_completed == 0
    assert status.phases_completed == 0
    assert status.next_open_step == "S02"


def test_enrichment_fields_serialise_to_json() -> None:
    """The new enrichment fields survive JSON round-tripping."""
    rng = random.Random(14)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=2)
    for step in spec.steps[:2]:
        step.checked = True
    plan = parse_plan(spec.render())

    payload = status_to_json_dict(collect_status(plan))
    restored = json.loads(json.dumps(payload))

    assert restored["waves_completed"] == 1
    assert restored["phases_completed"] == 1
    assert restored["next_open_step"] == "W02.P02.S03"


def test_status_collect_missing_exec_records(tmp_path: Path) -> None:
    """``collect_status`` finds checked plan steps lacking execution records."""
    body = (
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
        "## Phase `P01` - Test Phase\n"
        "- [x] `P01.S01` - Checked step with missing exec; `src/foo.py`.\n"
        "- [x] `P01.S02` - Checked step with existing exec; `src/bar.py`.\n"
        "- [ ] `P01.S03` - Unchecked step; `src/baz.py`.\n"
    )
    plan = parse_plan(body)

    # Prepare some directories
    exec_dir = tmp_path / ".vault" / "exec" / "2026-05-17-test-feature"
    exec_dir.mkdir(parents=True, exist_ok=True)

    # Write a valid exec doc with step_id: S02
    exec_file = exec_dir / "2026-05-17-test-feature-P01-S02.md"
    exec_file.write_text(
        "---\n"
        "tags:\n"
        "  - '#exec'\n"
        "  - '#test-feature'\n"
        "step_id: S02\n"
        "---\n"
        "\n"
        "Some execution details.",
        encoding="utf-8",
    )

    status = collect_status(plan, root_dir=tmp_path)

    assert status.exec_missing_ids == ["S01"]

    # Also assert JSON serialization of exec_missing_ids
    payload = status_to_json_dict(status)
    assert payload["exec_missing_ids"] == ["S01"]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestExecRecordIndexGraphParity:
    """``ExecRecordIndex.build(graph=...)`` matches the no-graph scan path."""

    def test_build_with_graph_matches_without(self, tmp_path: Path) -> None:
        from vaultspec_core.config import reset_config
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.plan.status import ExecRecordIndex

        reset_config()
        try:
            exec_dir = tmp_path / ".vault" / "exec" / "2026-05-17-test-feature"
            _write(
                exec_dir / "2026-05-17-test-feature-P01-S01.md",
                "---\ntags:\n  - '#exec'\n  - '#test-feature'\n"
                "step_id: 'S01'\n---\n\nBody.\n",
            )
            _write(
                exec_dir / "2026-05-17-test-feature-P01-S02.md",
                "---\ntags:\n  - '#exec'\n  - '#test-feature'\n"
                "step_id: 'S02'\n---\n\nBody.\n",
            )
            # An exec record with no resolvable step_id lands in the
            # unlinked bucket under both paths.
            _write(
                exec_dir / "2026-05-17-test-feature-orphan.md",
                "---\ntags:\n  - '#exec'\n  - '#test-feature'\n---\n\nBody.\n",
            )

            without_graph = ExecRecordIndex.build(tmp_path)
            graph = VaultGraph(tmp_path)
            with_graph = ExecRecordIndex.build(tmp_path, graph=graph)

            assert with_graph.by_step == without_graph.by_step
            assert with_graph.unlinked_by_feature == without_graph.unlinked_by_feature
            assert with_graph.by_step == {
                ("test-feature", "S01"): "2026-05-17-test-feature-P01-S01",
                ("test-feature", "S02"): "2026-05-17-test-feature-P01-S02",
            }
            assert with_graph.unlinked_by_feature == {
                "test-feature": ["2026-05-17-test-feature-orphan"]
            }
        finally:
            reset_config()


class TestCollectAllStatusesGraphParity:
    """``collect_all_statuses(graph=...)`` matches the no-graph scan path."""

    def test_collect_all_statuses_with_graph_matches_without(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.config import reset_config
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.plan.status import collect_all_statuses

        reset_config()
        try:
            _write(
                tmp_path / ".vault" / "plan" / "2026-05-17-alpha-plan.md",
                "---\ntags:\n  - '#plan'\n  - '#alpha'\ndate: '2026-05-17'\n"
                "tier: L1\n---\n\n# `alpha` plan\n\n"
                "- [x] `S01` - do the work; `src/a.py`.\n"
                "- [ ] `S02` - do more; `src/b.py`.\n",
            )
            _write(
                tmp_path
                / ".vault"
                / "exec"
                / "2026-05-17-alpha"
                / "2026-05-17-alpha-S01.md",
                "---\ntags:\n  - '#exec'\n  - '#alpha'\nstep_id: 'S01'\n---\n\nBody.\n",
            )

            without_graph = collect_all_statuses(tmp_path)
            graph = VaultGraph(tmp_path)
            with_graph = collect_all_statuses(tmp_path, graph=graph)

            assert len(with_graph) == len(without_graph) == 1
            a, b = with_graph[0], without_graph[0]
            assert a.document.name == b.document.name
            assert a.document.feature == b.document.feature
            assert a.document.date == b.document.date
            assert a.error == b.error is None
            assert a.status is not None and b.status is not None
            assert a.status.step_count == b.status.step_count == 2
            assert a.status.steps_completed == b.status.steps_completed == 1
            assert a.status.exec_missing_ids == b.status.exec_missing_ids == []
        finally:
            reset_config()


class TestExecRecordIndexLedger:
    """A consolidated ledger maps every Step it covers to one stem."""

    def test_ledger_registers_each_covered_step(self, tmp_path: Path) -> None:
        from vaultspec_core.config import reset_config
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.plan.status import ExecRecordIndex

        reset_config()
        try:
            exec_dir = tmp_path / ".vault" / "exec" / "2026-05-17-test-feature"
            _write(
                exec_dir / "2026-05-17-test-feature-ledger.md",
                "---\ntags:\n  - '#exec'\n  - '#test-feature'\n---\n\n"
                "# ledger\n\n## Changes\n\n"
                "- `S01` `M` `src/a.py`\n"
                "- `S01` `A` `tests/test_a.py`\n"
                "- `S02` `D` `src/b.py`\n",
            )

            without_graph = ExecRecordIndex.build(tmp_path)
            with_graph = ExecRecordIndex.build(tmp_path, graph=VaultGraph(tmp_path))

            stem = "2026-05-17-test-feature-ledger"
            expected = {
                ("test-feature", "S01"): stem,
                ("test-feature", "S02"): stem,
            }
            # Both build paths agree, and one document answers both Steps -
            # the per-Step cross-reference survives consolidation.
            assert without_graph.by_step == expected
            assert with_graph.by_step == expected
            assert without_graph.unlinked_by_feature == {}
            assert with_graph.unlinked_by_feature == {}
            assert without_graph.record_for("test-feature", "S02") == stem
        finally:
            reset_config()

    def test_ledger_naming_no_step_is_unlinked(self, tmp_path: Path) -> None:
        from vaultspec_core.config import reset_config
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.plan.status import ExecRecordIndex

        reset_config()
        try:
            exec_dir = tmp_path / ".vault" / "exec" / "2026-05-17-test-feature"
            _write(
                exec_dir / "2026-05-17-test-feature-ledger.md",
                "---\ntags:\n  - '#exec'\n  - '#test-feature'\n---\n\n"
                "# ledger\n\n## Changes\n\n- `M` `src/a.py`\n",
            )

            without_graph = ExecRecordIndex.build(tmp_path)
            with_graph = ExecRecordIndex.build(tmp_path, graph=VaultGraph(tmp_path))

            stem = "2026-05-17-test-feature-ledger"
            assert without_graph.by_step == {}
            assert without_graph.unlinked_by_feature == {"test-feature": [stem]}
            assert with_graph.unlinked_by_feature == {"test-feature": [stem]}
        finally:
            reset_config()
