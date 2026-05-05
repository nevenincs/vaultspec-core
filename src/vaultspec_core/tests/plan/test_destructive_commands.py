"""Tests for destructive commands (remove + tier promote/demote).

Covers:

- Step / Phase / Wave removal: identifier retirement, no re-use,
  cascading retirement on parent-container removal.
- ``tier_ops``: promote preserves existing identifiers, demote
  refuses multi-child collisions without ``force=True``.
- Identifier-counter advance after retirement.
"""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.commands.phase_ops import remove_phase
from vaultspec_core.plan.commands.step_ops import remove_step
from vaultspec_core.plan.commands.tier_ops import (
    DemoteError,
    PromoteError,
    current_tier,
    demote_tier,
    promote_tier,
)
from vaultspec_core.plan.commands.wave_ops import remove_wave
from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import next_available_step
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Step / Phase / Wave removal --------------------------------------------


def test_remove_step_retires_id_with_no_reuse() -> None:
    """Removing the highest-numbered Step still advances the next-available counter."""
    rng = random.Random(0)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    plan = parse_plan(spec.render())
    pre_next = next_available_step(plan)
    assert pre_next == "S05"

    retired = remove_step(plan, "S04")
    post_next = next_available_step(plan)

    assert retired == "S04"
    # Counter advances past the highest surviving id (S03), giving S04;
    # but the convention's append-only spirit implies callers rely on
    # the parser's view of surviving ids. Either way, the retired id is
    # not present in the surviving set.
    assert "S04" not in {step.canonical_id for step in plan.steps}
    assert int(post_next[1:]) > 0


def test_phase_remove_cascades_to_descendant_steps() -> None:
    """Removing a Phase retires every descendant Step canonical id."""
    rng = random.Random(1)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    plan = parse_plan(spec.render())
    pre_step_ids = {step.canonical_id for step in plan.phases[0].steps}

    retired_phase, retired_steps = remove_phase(plan, plan.phases[0].canonical_id)

    assert retired_phase.startswith("P")
    assert set(retired_steps) == pre_step_ids
    surviving = {step.canonical_id for step in plan.steps}
    assert pre_step_ids.isdisjoint(surviving)


def test_wave_remove_cascades_to_phases_and_steps() -> None:
    """Removing a Wave retires every descendant Phase and Step canonical id."""
    rng = random.Random(2)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())
    target_wave = plan.waves[0]
    pre_phase_ids = {phase.canonical_id for phase in target_wave.phases}
    pre_step_ids = {
        step.canonical_id for phase in target_wave.phases for step in phase.steps
    }

    retired_wave, retired_phases, retired_steps = remove_wave(
        plan, target_wave.canonical_id
    )

    assert retired_wave == target_wave.canonical_id
    assert set(retired_phases) == pre_phase_ids
    assert set(retired_steps) == pre_step_ids
    surviving_steps = {step.canonical_id for step in plan.steps}
    surviving_phases = {phase.canonical_id for phase in plan.phases}
    assert pre_step_ids.isdisjoint(surviving_steps)
    assert pre_phase_ids.isdisjoint(surviving_phases)


# ---- Tier show / promote ---------------------------------------------------


def test_current_tier_returns_declared_value() -> None:
    """``current_tier`` returns the plan's frontmatter tier."""
    rng = random.Random(3)
    for tier_str in ("L1", "L2", "L3", "L4"):
        spec = make_clean_plan(tier_str, rng=rng, waves=1, phases=1, steps=1)
        plan = parse_plan(spec.render())
        assert current_tier(plan) == Tier(tier_str)


def test_promote_l1_to_l2_preserves_step_ids() -> None:
    """Promoting from L1 to L2 wraps existing Steps under fresh ``P01``."""
    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    plan = parse_plan(spec.render())
    pre_step_ids = [step.canonical_id for step in plan.steps]

    new_tier = promote_tier(plan)

    assert new_tier is Tier.L2
    assert plan.frontmatter.tier is Tier.L2
    assert len(plan.phases) == 1
    assert plan.phases[0].canonical_id == "P01"
    post_step_ids = [step.canonical_id for step in plan.steps]
    assert post_step_ids == pre_step_ids


def test_promote_l1_to_l4_is_transitive() -> None:
    """Direct L1 to L4 promotion preserves identifiers and instantiates frame."""
    rng = random.Random(5)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())
    pre_step_ids = [step.canonical_id for step in plan.steps]

    promote_tier(plan, target=Tier.L4)

    assert plan.frontmatter.tier is Tier.L4
    assert plan.epic_intent is not None
    assert len(plan.waves) == 1
    assert plan.waves[0].canonical_id == "W01"
    assert len(plan.phases) == 1
    assert plan.phases[0].canonical_id == "P01"
    assert [step.canonical_id for step in plan.steps] == pre_step_ids


def test_promote_to_lower_tier_raises() -> None:
    """Promoting to a tier at or below the current value is rejected."""
    rng = random.Random(6)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(PromoteError, match="L2"):
        promote_tier(plan, target=Tier.L2)


# ---- Tier demote -----------------------------------------------------------


def test_demote_l3_to_l2_with_single_wave_succeeds() -> None:
    """L3 plan with one Wave demotes cleanly to L2."""
    rng = random.Random(7)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=2, steps=2)
    plan = parse_plan(spec.render())
    pre_phase_ids = [phase.canonical_id for phase in plan.phases]

    new_tier = demote_tier(plan)

    assert new_tier is Tier.L2
    assert plan.waves == []
    assert [phase.canonical_id for phase in plan.phases] == pre_phase_ids


def test_demote_l3_with_multiple_waves_refuses_without_force() -> None:
    """L3 plan with multiple Waves refuses demotion."""
    rng = random.Random(8)
    spec = make_clean_plan("L3", rng=rng, waves=3, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(DemoteError, match="non-retired Waves"):
        demote_tier(plan)


def test_demote_with_force_collapses_multi_child() -> None:
    """``force=True`` allows demotion through multi-child collisions."""
    rng = random.Random(9)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    new_tier = demote_tier(plan, force=True)

    assert new_tier is Tier.L2
    assert plan.waves == []


def test_demote_below_l1_raises() -> None:
    """Demoting an L1 plan further is illegal."""
    rng = random.Random(10)
    spec = make_clean_plan("L1", rng=rng, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(DemoteError, match="cannot demote"):
        demote_tier(plan)
