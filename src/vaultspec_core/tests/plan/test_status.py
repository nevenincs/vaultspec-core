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
