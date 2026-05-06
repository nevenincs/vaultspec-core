"""Tests for additive write commands: step / phase / wave add and insert."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.commands.phase_ops import (
    AddPhaseError,
    add_phase,
    insert_phase,
)
from vaultspec_core.plan.commands.step_ops import AddStepError, add_step, insert_step
from vaultspec_core.plan.commands.wave_ops import AddWaveError, add_wave, insert_wave
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Step add ---------------------------------------------------------------


def test_add_step_l1_appends_at_next_available() -> None:
    """L1 step add returns the next-available ``S##``."""
    rng = random.Random(0)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    plan = parse_plan(spec.render())

    new_step = add_step(plan, action="rewrite docs", scope="docs/index.md")

    assert new_step.canonical_id == "S04"
    assert plan.steps[-1] is new_step


def test_add_step_l2_requires_phase_id() -> None:
    """L2 step add without --phase raises an explicit error."""
    rng = random.Random(1)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())

    with pytest.raises(AddStepError, match="--phase"):
        add_step(plan, action="rewrite", scope="src/a.py")


def test_add_step_l2_appends_to_named_phase() -> None:
    """L2 step add with --phase places the new Step in that Phase."""
    rng = random.Random(2)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    target_phase = plan.phases[1]
    pre_count = len(target_phase.steps)

    new_step = add_step(
        plan, action="add tests", scope="tests/", phase_id=target_phase.canonical_id
    )

    assert new_step in target_phase.steps
    assert len(target_phase.steps) == pre_count + 1
    assert (
        new_step.display_path == f"{target_phase.canonical_id}.{new_step.canonical_id}"
    )


def test_add_step_unknown_phase_raises() -> None:
    """L2 step add with a non-existent phase id errors clearly."""
    rng = random.Random(3)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(AddStepError, match="P99"):
        add_step(plan, action="x", scope="src/x.py", phase_id="P99")


def test_add_step_preserves_existing_canonical_ids() -> None:
    """Adding a Step never renumbers existing rows."""
    rng = random.Random(4)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=2, steps=2)
    plan = parse_plan(spec.render())
    pre_ids = [s.canonical_id for s in plan.steps]
    target_phase = plan.phases[0]

    add_step(
        plan, action="extend", scope="src/x.py", phase_id=target_phase.canonical_id
    )

    post_ids = [s.canonical_id for s in plan.steps]
    assert post_ids[: len(pre_ids)] == pre_ids


# ---- Step insert ------------------------------------------------------------


def test_insert_step_before_anchor_places_in_doc_order() -> None:
    """``insert --before S02`` places the new row immediately before S02."""
    rng = random.Random(5)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    plan = parse_plan(spec.render())

    new_step = insert_step(plan, action="x", scope="src/x.py", before="S02")

    canonical_ids = [s.canonical_id for s in plan.steps]
    assert canonical_ids.index(new_step.canonical_id) < canonical_ids.index("S02")


def test_insert_step_after_anchor_places_in_doc_order() -> None:
    """``insert --after S02`` places the new row immediately after S02."""
    rng = random.Random(6)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    plan = parse_plan(spec.render())

    new_step = insert_step(plan, action="x", scope="src/x.py", after="S02")

    canonical_ids = [s.canonical_id for s in plan.steps]
    assert canonical_ids.index(new_step.canonical_id) == canonical_ids.index("S02") + 1


def test_insert_step_requires_exactly_one_anchor() -> None:
    """Neither anchor or both anchors raises a typed error."""
    rng = random.Random(7)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())

    with pytest.raises(AddStepError, match="--before or --after"):
        insert_step(plan, action="x", scope="src/x.py")
    with pytest.raises(AddStepError, match="at most one"):
        insert_step(plan, action="x", scope="src/x.py", before="S01", after="S02")


def test_insert_step_inherits_anchor_phase_at_l2() -> None:
    """At L2, the new Step inherits the anchor's parent Phase."""
    rng = random.Random(8)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    anchor_phase = plan.phases[0]
    anchor_step = anchor_phase.steps[0]

    new_step = insert_step(
        plan, action="x", scope="src/x.py", before=anchor_step.canonical_id
    )

    assert new_step in anchor_phase.steps
    assert new_step.display_path.startswith(anchor_phase.canonical_id)


# ---- Phase add / insert -----------------------------------------------------


def test_add_phase_l2_appends() -> None:
    """L2 phase add places the new Phase at the next-available ``P##``."""
    rng = random.Random(9)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=1)
    plan = parse_plan(spec.render())

    new_phase = add_phase(plan, title="extra phase", intent="Adds coverage.")

    assert new_phase.canonical_id == "P03"
    assert new_phase in plan.phases


def test_add_phase_l3_requires_wave_id() -> None:
    """L3 phase add without --wave raises an explicit error."""
    rng = random.Random(10)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(AddPhaseError, match="--wave"):
        add_phase(plan, title="x", intent="x")


def test_add_phase_l3_attaches_to_named_wave() -> None:
    """L3 phase add with --wave attaches the Phase under the named Wave."""
    rng = random.Random(11)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())
    target_wave = plan.waves[1]

    new_phase = add_phase(plan, title="x", intent="x", wave_id=target_wave.canonical_id)

    assert new_phase in target_wave.phases


def test_insert_phase_inherits_anchor_wave_at_l3() -> None:
    """L3 phase insert inherits the anchor Phase's parent Wave."""
    rng = random.Random(12)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=1)
    plan = parse_plan(spec.render())
    anchor_wave = plan.waves[0]
    anchor_phase = anchor_wave.phases[0]

    new_phase = insert_phase(
        plan, title="x", intent="x", before=anchor_phase.canonical_id
    )

    assert new_phase in anchor_wave.phases


# ---- Wave add / insert ------------------------------------------------------


def test_add_wave_l3_appends() -> None:
    """L3 wave add places the new Wave at the next-available ``W##``."""
    rng = random.Random(13)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    new_wave = add_wave(plan, title="extra wave", intent="Adds another batch.")

    assert new_wave.canonical_id == "W03"
    assert new_wave in plan.waves


def test_add_wave_l1_l2_rejected() -> None:
    """L1 and L2 plans do not support Wave additions."""
    rng = random.Random(14)
    for tier in ("L1", "L2"):
        spec = make_clean_plan(tier, rng=rng, phases=1, steps=1)
        plan = parse_plan(spec.render())
        with pytest.raises(AddWaveError, match="L"):
            add_wave(plan, title="x", intent="x")


def test_insert_wave_before_anchor_places_in_doc_order() -> None:
    """``insert_wave --before W02`` places the Wave just before W02."""
    rng = random.Random(15)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    new_wave = insert_wave(plan, title="x", intent="x", before="W02")

    canonical_ids = [w.canonical_id for w in plan.waves]
    assert canonical_ids.index(new_wave.canonical_id) + 1 == canonical_ids.index("W02")


# ---- Identifier-immutability invariant under additive operations -----------


@pytest.mark.parametrize("seed", range(8))
def test_random_additive_sequence_preserves_existing_canonical_ids(seed: int) -> None:
    """Sequential add+insert operations never renumber existing rows."""
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    pre_ids = [s.canonical_id for s in plan.steps]
    target_phase = plan.phases[0]

    for _ in range(rng.randint(2, 5)):
        add_step(plan, action="x", scope="src/x.py", phase_id=target_phase.canonical_id)

    post_ids = [s.canonical_id for s in plan.steps]
    assert post_ids[: len(pre_ids)] == pre_ids
