"""Tests for the plan-query selector + predicate machinery."""

from __future__ import annotations

import random

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.query import QueryFilter, query_steps
from vaultspec_core.tests.plan._factories import make_clean_plan


def test_unfiltered_query_returns_every_step() -> None:
    """An empty filter returns every Step in the plan."""
    rng = random.Random(0)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    result = query_steps(plan, QueryFilter())

    assert len(result.matched) == result.total == len(plan.steps)


def test_phase_selector_restricts_to_phase_subtree() -> None:
    """``scope_phase`` returns only the Steps under the named Phase."""
    rng = random.Random(1)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    plan = parse_plan(spec.render())
    target_phase = plan.phases[0]

    result = query_steps(
        plan,
        QueryFilter(scope_phase=target_phase.canonical_id),
    )

    assert len(result.matched) == len(target_phase.steps)
    assert all(
        step.canonical_id in {s.canonical_id for s in target_phase.steps}
        for step in result.matched
    )


def test_wave_selector_restricts_to_wave_subtree() -> None:
    """``scope_wave`` returns every Step under the named Wave's Phases."""
    rng = random.Random(2)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())
    target_wave = plan.waves[0]
    expected_steps = [step for phase in target_wave.phases for step in phase.steps]

    result = query_steps(
        plan,
        QueryFilter(scope_wave=target_wave.canonical_id),
    )

    assert len(result.matched) == len(expected_steps)


def test_open_predicate_filters_to_open_steps() -> None:
    """``only_open=True`` excludes closed Steps."""
    rng = random.Random(3)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    spec.steps[0].checked = True
    spec.steps[2].checked = True
    plan = parse_plan(spec.render())

    result = query_steps(plan, QueryFilter(only_open=True))

    assert len(result.matched) == 2
    assert all(not step.checked for step in result.matched)


def test_closed_predicate_filters_to_closed_steps() -> None:
    """``only_closed=True`` excludes open Steps."""
    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    spec.steps[1].checked = True
    plan = parse_plan(spec.render())

    result = query_steps(plan, QueryFilter(only_closed=True))

    assert len(result.matched) == 1
    assert all(step.checked for step in result.matched)


def test_tier_match_returns_empty_when_tier_differs() -> None:
    """``tier_match`` returns an empty result when the plan tier differs."""
    rng = random.Random(5)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=2)
    plan = parse_plan(spec.render())

    result = query_steps(plan, QueryFilter(tier_match=Tier.L4))

    assert result.matched == []
    assert result.total == len(plan.steps)


def test_phase_selector_wins_over_wave_selector() -> None:
    """When both ``scope_phase`` and ``scope_wave`` are set, Phase wins."""
    rng = random.Random(6)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())
    target_phase = plan.phases[0]

    result = query_steps(
        plan,
        QueryFilter(
            scope_wave=plan.waves[1].canonical_id,
            scope_phase=target_phase.canonical_id,
        ),
    )

    assert len(result.matched) == len(target_phase.steps)


def test_unknown_phase_selector_returns_empty_match() -> None:
    """Selectors referencing missing identifiers return no matches."""
    rng = random.Random(7)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=1)
    plan = parse_plan(spec.render())

    result = query_steps(plan, QueryFilter(scope_phase="P99"))

    assert result.matched == []
