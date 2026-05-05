"""Tests for state and re-parenting commands across step / phase / wave / epic."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.commands.epic_ops import (
    EpicIntentError,
    edit_epic_intent,
    show_epic_intent,
)
from vaultspec_core.plan.commands.phase_ops import (
    MovePhaseError,
    PhaseNotFoundError,
    edit_phase,
    move_phase,
)
from vaultspec_core.plan.commands.step_ops import (
    MoveStepError,
    StepNotFoundError,
    check_step,
    edit_step,
    move_step,
    toggle_step,
    uncheck_step,
)
from vaultspec_core.plan.commands.wave_ops import (
    MoveWaveError,
    WaveNotFoundError,
    edit_wave,
    move_wave,
)
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Step state -------------------------------------------------------------


def test_toggle_flips_checkbox_state() -> None:
    """``toggle`` flips open <-> closed."""
    rng = random.Random(0)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())
    assert plan.steps[0].checked is False

    toggled = toggle_step(plan, plan.steps[0].canonical_id)

    assert toggled.checked is True
    toggle_step(plan, plan.steps[0].canonical_id)
    assert plan.steps[0].checked is False


def test_check_is_idempotent() -> None:
    """``check`` always sets ``checked=True``."""
    rng = random.Random(1)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())

    check_step(plan, "S01")
    check_step(plan, "S01")

    assert plan.steps[0].checked is True


def test_uncheck_is_idempotent() -> None:
    """``uncheck`` always sets ``checked=False``."""
    rng = random.Random(2)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    spec.steps[0].checked = True
    plan = parse_plan(spec.render())

    uncheck_step(plan, "S01")
    uncheck_step(plan, "S01")

    assert plan.steps[0].checked is False


def test_step_state_ops_raise_on_unknown_id() -> None:
    """All state ops raise :class:`StepNotFoundError` on missing ids."""
    rng = random.Random(3)
    spec = make_clean_plan("L1", rng=rng, steps=1)
    plan = parse_plan(spec.render())

    for op in (toggle_step, check_step, uncheck_step):
        with pytest.raises(StepNotFoundError, match="S99"):
            op(plan, "S99")


def test_edit_step_action_only() -> None:
    """``edit_step(action=...)`` updates only the action, leaves scope intact."""
    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())
    original_scope = plan.steps[0].scope

    edit_step(plan, "S01", action="updated action")

    assert plan.steps[0].action == "updated action"
    assert plan.steps[0].scope == original_scope


# ---- Step move --------------------------------------------------------------


def test_move_step_to_phase_re_parents_with_path_recompute() -> None:
    """Re-parenting recomputes the display path against the new Phase."""
    rng = random.Random(5)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    moving = plan.phases[0].steps[0]
    dest_phase = plan.phases[1]

    moved = move_step(plan, moving.canonical_id, to_phase=dest_phase.canonical_id)

    assert moved in dest_phase.steps
    assert moving not in plan.phases[0].steps
    assert moved.display_path == f"{dest_phase.canonical_id}.{moved.canonical_id}"


def test_move_step_before_anchor_in_same_parent() -> None:
    """``move --before S##`` re-positions within the current parent."""
    rng = random.Random(6)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=4)
    plan = parse_plan(spec.render())
    phase = plan.phases[0]

    move_step(plan, "S04", before="S02")

    canonical_ids = [s.canonical_id for s in phase.steps]
    assert canonical_ids.index("S04") < canonical_ids.index("S02")


def test_move_step_cross_parent_with_anchor_outside_dest_raises() -> None:
    """Anchor must reside in the destination Phase post-move."""
    rng = random.Random(7)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())
    moving = plan.phases[0].steps[0]
    other_phase = plan.phases[1]
    anchor_in_origin = plan.phases[0].steps[1]

    with pytest.raises(MoveStepError, match="destination phase"):
        move_step(
            plan,
            moving.canonical_id,
            to_phase=other_phase.canonical_id,
            before=anchor_in_origin.canonical_id,
        )


def test_move_step_requires_some_argument() -> None:
    """``move`` with no flags raises a typed error."""
    rng = random.Random(8)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan = parse_plan(spec.render())

    with pytest.raises(MoveStepError, match="--to-phase"):
        move_step(plan, "S01")


# ---- Phase edit / move ------------------------------------------------------


def test_edit_phase_title_and_intent() -> None:
    """``edit_phase`` updates title and / or intent."""
    rng = random.Random(9)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=1)
    plan = parse_plan(spec.render())

    edit_phase(plan, "P01", title="new title", intent="new intent paragraph.")

    assert plan.phases[0].title == "new title"
    assert plan.phases[0].intent == "new intent paragraph."


def test_edit_phase_unknown_id_raises() -> None:
    """``edit_phase`` raises on missing ids."""
    rng = random.Random(10)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(PhaseNotFoundError, match="P99"):
        edit_phase(plan, "P99", title="x")


def test_move_phase_re_parents_with_descendant_path_recompute() -> None:
    """Re-parenting a Phase recomputes child Step display paths."""
    rng = random.Random(11)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=2)
    plan = parse_plan(spec.render())
    moving_phase = plan.waves[0].phases[0]
    dest_wave = plan.waves[1]

    move_phase(plan, moving_phase.canonical_id, to_wave=dest_wave.canonical_id)

    assert moving_phase in dest_wave.phases
    for step in moving_phase.steps:
        assert step.display_path.startswith(dest_wave.canonical_id)


def test_move_phase_requires_some_argument() -> None:
    """``move_phase`` with no flags raises."""
    rng = random.Random(12)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(MovePhaseError, match="--to-wave"):
        move_phase(plan, plan.phases[0].canonical_id)


# ---- Wave edit / move -------------------------------------------------------


def test_edit_wave_title_and_intent() -> None:
    """``edit_wave`` updates title and / or intent."""
    rng = random.Random(13)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    edit_wave(plan, "W01", title="new wave title", intent="new wave intent.")

    assert plan.waves[0].title == "new wave title"
    assert plan.waves[0].intent == "new wave intent."


def test_edit_wave_unknown_id_raises() -> None:
    """``edit_wave`` raises on missing ids."""
    rng = random.Random(14)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(WaveNotFoundError, match="W99"):
        edit_wave(plan, "W99", title="x")


def test_move_wave_repositions_in_doc_order_with_descendant_path_recompute() -> None:
    """``move_wave`` re-positions and refreshes descendant paths."""
    rng = random.Random(15)
    spec = make_clean_plan("L3", rng=rng, waves=3, phases=1, steps=1)
    plan = parse_plan(spec.render())

    move_wave(plan, "W03", before="W01")

    canonical_ids = [w.canonical_id for w in plan.waves]
    assert canonical_ids[0] == "W03"
    moved = plan.waves[0]
    for phase in moved.phases:
        for step in phase.steps:
            assert step.display_path.startswith("W03")


def test_move_wave_unknown_anchor_raises() -> None:
    """``move_wave`` rejects a missing anchor."""
    rng = random.Random(16)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(MoveWaveError, match="W99"):
        move_wave(plan, "W01", before="W99")


# ---- Epic intent ------------------------------------------------------------


def test_show_epic_intent_returns_text_at_l4() -> None:
    """``show_epic_intent`` returns the L4 plan's intent paragraph."""
    rng = random.Random(17)
    spec = make_clean_plan("L4", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    text = show_epic_intent(plan)

    assert text  # non-empty
    assert plan.epic_intent is not None
    assert text == plan.epic_intent.text


def test_edit_epic_intent_replaces_text() -> None:
    """``edit_epic_intent`` replaces the paragraph in place."""
    rng = random.Random(18)
    spec = make_clean_plan("L4", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    edit_epic_intent(plan, text="New PM association: roadmap GROWTH-2026.")

    assert plan.epic_intent is not None
    assert plan.epic_intent.text == "New PM association: roadmap GROWTH-2026."


@pytest.mark.parametrize("tier", ["L1", "L2", "L3"])
def test_epic_intent_ops_reject_non_l4_plans(tier: str) -> None:
    """Epic intent show / edit refuse to run against non-L4 plans."""
    rng = random.Random(19)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(EpicIntentError, match="L4"):
        show_epic_intent(plan)
    with pytest.raises(EpicIntentError, match="L4"):
        edit_epic_intent(plan, text="x")


def test_move_step_rejects_self_anchor() -> None:
    """``move_step`` must refuse to move a Step relative to itself.

    Regression for the silent-corruption flaw where the anchor lookup ran
    after the moving Step had already been removed from the list, returning
    a stale or invalid index.
    """
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(101)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=3)
    plan = parse_plan(spec.render())

    with pytest.raises(MoveStepError, match="relative to itself"):
        move_step(plan, "S01", before="S01")
    with pytest.raises(MoveStepError, match="relative to itself"):
        move_step(plan, "S02", after="S02")


def test_move_phase_rejects_self_anchor() -> None:
    """``move_phase`` must refuse to move a Phase relative to itself."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(102)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=2, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(MovePhaseError, match="relative to itself"):
        move_phase(plan, "P01", before="P01")
    with pytest.raises(MovePhaseError, match="relative to itself"):
        move_phase(plan, "P02", after="P02")


def test_move_wave_rejects_self_anchor() -> None:
    """``move_wave`` must refuse to move a Wave relative to itself."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(103)
    spec = make_clean_plan("L3", rng=rng, waves=3, phases=1, steps=1)
    plan = parse_plan(spec.render())

    with pytest.raises(MoveWaveError, match="relative to itself"):
        move_wave(plan, "W01", before="W01")
    with pytest.raises(MoveWaveError, match="relative to itself"):
        move_wave(plan, "W02", after="W02")
