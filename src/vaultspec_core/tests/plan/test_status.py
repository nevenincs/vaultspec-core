"""Tests for plan-status snapshot collection and JSON emission."""

from __future__ import annotations

import json
import random

import pytest

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
