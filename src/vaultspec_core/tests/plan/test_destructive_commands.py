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
    """Removing the highest-numbered Step retires the id; counter never reuses it.

    Per the convention's append-only / no-reuse contract, removing ``S04`` from
    a plan with ``S01..S04`` must leave ``next_available_step`` returning
    ``S05``, not ``S04``. The retirement set persists across parse / serialise
    round-trips via the hidden ``<!-- RETIRED: ... -->`` ledger.
    """
    rng = random.Random(0)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    plan = parse_plan(spec.render())
    pre_next = next_available_step(plan)
    assert pre_next == "S05"

    retired = remove_step(plan, "S04")
    post_next = next_available_step(plan)

    assert retired == "S04"
    assert "S04" not in {step.canonical_id for step in plan.steps}
    assert "S04" in plan.retired_step_ids
    assert post_next == "S05"


def test_retired_step_id_persists_across_round_trip() -> None:
    """Retired Step ids survive parse → serialise → parse."""
    from vaultspec_core.plan.serialiser import serialise_plan

    rng = random.Random(20)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    plan = parse_plan(spec.render())
    remove_step(plan, "S04")

    serialised = serialise_plan(plan)
    reparsed = parse_plan(serialised)

    assert reparsed.retired_step_ids == {"S04"}
    assert next_available_step(reparsed) == "S05"


def test_retired_phase_id_persists_across_round_trip() -> None:
    """Retired Phase ids and their cascaded Steps survive a round-trip."""
    from vaultspec_core.plan.commands.phase_ops import remove_phase
    from vaultspec_core.plan.serialiser import serialise_plan

    rng = random.Random(21)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    target_phase = plan.phases[0].canonical_id
    target_steps = {step.canonical_id for step in plan.phases[0].steps}

    remove_phase(plan, target_phase)
    reparsed = parse_plan(serialise_plan(plan))

    assert target_phase in reparsed.retired_phase_ids
    assert target_steps <= reparsed.retired_step_ids


def test_demote_retires_dropped_wave_ids() -> None:
    """Demoting L3 -> L2 retires every Wave canonical id it discards."""
    rng = random.Random(22)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())
    pre_wave_ids = {wave.canonical_id for wave in plan.waves}

    demote_tier(plan, force=True)

    assert pre_wave_ids <= plan.retired_wave_ids
    assert plan.waves == []


def test_renumber_phase_reassigns_canonical_id_and_recomputes_paths() -> None:
    """``renumber_phase`` rewrites canonical id, display path, and Step paths."""
    from vaultspec_core.plan.commands.phase_ops import renumber_phase

    rng = random.Random(40)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())
    # W02's first phase carries canonical id P03 (W01 had P01, P02).
    target_phase = plan.waves[1].phases[0]
    pre_steps_under_target = [step.canonical_id for step in target_phase.steps]

    renumber_phase(plan, plan.waves[1].phases[0].canonical_id, to="P99")

    target_phase = plan.waves[1].phases[0]
    assert target_phase.canonical_id == "P99"
    assert target_phase.display_path == "W02.P99"
    for step in target_phase.steps:
        assert step.display_path.startswith("W02.P99.")
    assert [step.canonical_id for step in target_phase.steps] == pre_steps_under_target


def test_renumber_phase_rejects_collision_with_live_id() -> None:
    """Renumber refuses a target id already in use by another live Phase."""
    from vaultspec_core.plan.commands.phase_ops import (
        PhaseRenumberError,
        renumber_phase,
    )

    rng = random.Random(41)
    spec = make_clean_plan("L2", rng=rng, phases=3, steps=1)
    plan = parse_plan(spec.render())
    live_other = plan.phases[1].canonical_id

    with pytest.raises(PhaseRenumberError, match="collides"):
        renumber_phase(plan, plan.phases[0].canonical_id, to=live_other)


def test_renumber_phase_in_collision_does_not_retire_still_live_id() -> None:
    """Renumbering a colliding twin must NOT retire the id used by the survivor.

    Regression for H-CLOSEOUT-1: ``renumber_phase`` was unconditionally
    adding the old id to ``plan.retired_phase_ids``. In the verb's primary
    documented use case (remediating an authoring collision where two
    containers carried the same canonical Phase id), the "old" id is still
    live in the other container after the rename. Adding it to retired
    would mark a live id as retired, blocking valid future allocations.
    """
    from vaultspec_core.plan.commands.phase_ops import renumber_phase

    rng = random.Random(60)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=1)
    plan = parse_plan(spec.render())
    # Fabricate a duplicated id by direct mutation: give one of W02's
    # Phases the same canonical id as the first W01 Phase.
    duplicated_id = plan.waves[0].phases[0].canonical_id
    target = plan.waves[1].phases[0]
    target.canonical_id = duplicated_id
    target.display_path = f"{plan.waves[1].canonical_id}.{duplicated_id}"

    renumber_phase(plan, duplicated_id, to="P99")

    # The renamed phase moved to P99; the duplicated id remains live in W01.
    assert any(p.canonical_id == "P99" for p in plan.phases)
    assert any(p.canonical_id == duplicated_id for p in plan.phases)
    # Retirement set must NOT contain the still-live id.
    assert duplicated_id not in plan.retired_phase_ids


def test_renumber_phase_in_simple_rename_does_retire_old_id() -> None:
    """Renumbering a unique id (no collision) retires it as expected."""
    from vaultspec_core.plan.commands.phase_ops import renumber_phase

    rng = random.Random(61)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=1)
    plan = parse_plan(spec.render())
    unique_old = plan.phases[0].canonical_id

    renumber_phase(plan, unique_old, to="P99")

    assert "P99" in {p.canonical_id for p in plan.phases}
    # Old id is no longer live anywhere -> should be retired.
    assert unique_old in plan.retired_phase_ids


def test_renumber_phase_rejects_retired_target_id() -> None:
    """Renumber refuses a target id sitting in the retirement set."""
    from vaultspec_core.plan.commands.phase_ops import (
        PhaseRenumberError,
        remove_phase,
        renumber_phase,
    )

    rng = random.Random(42)
    spec = make_clean_plan("L2", rng=rng, phases=3, steps=1)
    plan = parse_plan(spec.render())
    retired = plan.phases[2].canonical_id
    remove_phase(plan, retired)

    with pytest.raises(PhaseRenumberError, match="retired"):
        renumber_phase(plan, plan.phases[0].canonical_id, to=retired)


def test_retirement_ledger_is_not_absorbed_into_phase_intent() -> None:
    """A ledger comment placed inside an intent block must not pollute intent text.

    Regression for the H-NEW-1 finding: ``_walk_body`` previously appended
    every non-heading non-row line into the active intent buffer, including
    a hand-edited or stray ``<!-- RETIRED: ... -->`` block. The next
    serialise pass would then re-emit the canonical ledger AND the absorbed
    duplicate inside the intent paragraph, polluting authored prose and
    accumulating on every round-trip.
    """
    from vaultspec_core.plan.serialiser import serialise_plan

    rng = random.Random(50)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=2)
    rendered = spec.render()
    # Inject a ledger comment INSIDE the Phase intent block (after heading,
    # before first Step row).
    polluted = rendered.replace(
        "Phase P01 delivers a coherent slice of the work.",
        "Phase P01 delivers a coherent slice of the work.\n<!-- RETIRED: S99 -->",
    )

    plan = parse_plan(polluted)

    # Intent must not contain the ledger marker.
    assert "RETIRED:" not in plan.phases[0].intent
    # But the ledger token must still be parsed into the retirement set.
    assert "S99" in plan.retired_step_ids
    # Round-trip emits exactly one ledger comment, not two.
    serialised = serialise_plan(plan)
    assert serialised.count("<!-- RETIRED:") == 1


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
