"""Round-trip tests for the plan serialiser.

Asserts ``parse -> serialise -> parse`` yields an equivalent model
across every tier, plus targeted invariants on the serialised text.
"""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Core round-trip --------------------------------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_round_trip_preserves_step_canonical_ids(tier: str) -> None:
    """``parse -> serialise -> parse`` yields the same canonical Step ids."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=3)

    first = parse_plan(spec.render())
    rendered = serialise_plan(first)
    second = parse_plan(rendered)

    assert [s.canonical_id for s in first.steps] == [
        s.canonical_id for s in second.steps
    ]


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_round_trip_preserves_step_actions_and_scopes(tier: str) -> None:
    """Every Step's action statement and scope round-trip unchanged."""
    rng = random.Random(1)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=2, steps=3)

    first = parse_plan(spec.render())
    rendered = serialise_plan(first)
    second = parse_plan(rendered)

    for original, restored in zip(first.steps, second.steps, strict=True):
        assert original.action == restored.action
        assert original.scope == restored.scope


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_round_trip_preserves_step_checked_state(tier: str) -> None:
    """Closed Steps (``[x]``) round-trip; open Steps (``[ ]``) round-trip."""
    rng = random.Random(2)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=2, steps=2)
    # Mark every other Step closed to exercise both states.
    for index, step in enumerate(spec.steps):
        step.checked = index % 2 == 0

    first = parse_plan(spec.render())
    rendered = serialise_plan(first)
    second = parse_plan(rendered)

    assert [s.checked for s in first.steps] == [s.checked for s in second.steps]


def test_round_trip_preserves_l4_epic_intent_text() -> None:
    """L4 plans round-trip with the Epic intent paragraph intact."""
    rng = random.Random(3)
    spec = make_clean_plan("L4", rng=rng, waves=2, phases=2, steps=2)

    first = parse_plan(spec.render())
    rendered = serialise_plan(first)
    second = parse_plan(rendered)

    assert first.epic_intent is not None
    assert second.epic_intent is not None
    assert first.epic_intent.text == second.epic_intent.text


@pytest.mark.parametrize("tier", ["L1", "L2", "L3"])
def test_round_trip_lower_tiers_have_no_epic_intent(tier: str) -> None:
    """L1, L2, L3 round-trips never introduce an Epic intent block."""
    rng = random.Random(4)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=2)

    first = parse_plan(spec.render())
    rendered = serialise_plan(first)
    second = parse_plan(rendered)

    assert first.epic_intent is None
    assert second.epic_intent is None


# ---- Frontmatter shape ------------------------------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_serialised_frontmatter_emits_unquoted_tier_scalar(tier: str) -> None:
    """The serialiser writes ``tier: L#`` as an unquoted scalar."""
    rng = random.Random(5)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    rendered = serialise_plan(plan)

    assert f"tier: {tier}\n" in rendered


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_serialised_related_uses_single_quoted_wikilinks(tier: str) -> None:
    """``related`` entries render as single-quoted wiki-links per the convention."""
    rng = random.Random(6)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    rendered = serialise_plan(plan)

    assert "related:" in rendered
    assert "  - '[[2026-05-05-test-feature-adr]]'" in rendered


# ---- Stability under randomised parameters ----------------------------------


@pytest.mark.parametrize("seed", range(20))
def test_round_trip_is_idempotent_under_random_clean_plans(seed: int) -> None:
    """Twenty random seeds, four tiers: parse/serialise/parse is byte-stable
    on the second iteration.

    The first parse may discard non-canonical whitespace; once
    serialised, the canonical form round-trips byte-for-byte through
    every subsequent iteration.
    """
    rng = random.Random(seed)
    tier = rng.choice(["L1", "L2", "L3", "L4"])
    spec = make_clean_plan(
        tier,
        rng=rng,
        waves=rng.randint(1, 3),
        phases=rng.randint(1, 3),
        steps=rng.randint(1, 4),
    )
    plan = parse_plan(spec.render())

    canonical_text = serialise_plan(plan)
    re_parsed = parse_plan(canonical_text)
    second_canonical = serialise_plan(re_parsed)

    assert canonical_text == second_canonical
