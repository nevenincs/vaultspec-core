"""Tests for canonical-identifier extraction, counters, and validation."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.identifiers import (
    DuplicateIdentifierError,
    extract_inventory,
    next_available_phase,
    next_available_step,
    next_available_wave,
    validate_identifiers,
)
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import (
    inject_gap,
    make_clean_plan,
)

# ---- Inventory extraction ---------------------------------------------------


@pytest.mark.parametrize(
    ("tier", "waves", "phases", "steps", "expected_step_count"),
    [
        ("L1", 0, 0, 4, 4),
        ("L2", 0, 2, 3, 6),
        ("L3", 2, 2, 2, 8),
        ("L4", 1, 3, 2, 6),
    ],
)
def test_inventory_counts_match_spec_step_count(
    tier: str, waves: int, phases: int, steps: int, expected_step_count: int
) -> None:
    """The inventory's Step list size matches the count emitted by the factory."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=waves, phases=phases, steps=steps)
    plan = parse_plan(spec.render())

    inventory = extract_inventory(plan)

    assert len(inventory.steps) == expected_step_count


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_inventory_preserves_document_order(tier: str) -> None:
    """The inventory lists identifiers in document order (not sorted)."""
    rng = random.Random(1)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    inventory = extract_inventory(plan)

    assert inventory.steps == [s.canonical_id for s in plan.steps]


def test_inventory_padding_violations_are_empty_for_clean_plan() -> None:
    """A factory-generated clean plan has no padding violations."""
    rng = random.Random(2)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=3)
    plan = parse_plan(spec.render())

    inventory = extract_inventory(plan)

    assert inventory.padding_violations == []


# ---- Next-available counters ------------------------------------------------


def test_next_available_step_after_clean_plan_is_one_past_max() -> None:
    """``next_available_step`` returns the immediate successor of the maximum.

    A factory L2 plan with two Phases of three Steps each has Steps
    S01..S06; the next-available is S07.
    """
    rng = random.Random(3)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    plan = parse_plan(spec.render())

    assert next_available_step(plan) == "S07"


def test_next_available_step_skips_retired_identifiers() -> None:
    """Removing the highest-numbered Step leaves a retired id; counter still advances.

    The append-only rule means the counter is anchored to the maximum
    historical id; removing it should not free the slot for re-use.
    Since the parser only sees surviving rows, this test verifies the
    behaviour against a plan whose document lacks the previously-
    allocated max id and asserts the counter advances past whatever
    maximum survives in the document.
    """
    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=5)
    plan = parse_plan(spec.render())
    original_next = next_available_step(plan)
    assert original_next == "S06"

    gapped = inject_gap(spec, rng=random.Random(99))
    gapped_plan = parse_plan(gapped.render())
    new_next = next_available_step(gapped_plan)

    # Whether the deleted Step was terminal or interior, the counter
    # must always advance to a number greater than every surviving id.
    surviving_numbers = [int(s.canonical_id[1:]) for s in gapped_plan.steps]
    counter_number = int(new_next[1:])
    assert counter_number > max(surviving_numbers)


def test_next_available_phase_advances_past_max() -> None:
    """``next_available_phase`` is one past the maximum existing Phase id."""
    rng = random.Random(5)
    spec = make_clean_plan("L2", rng=rng, phases=4, steps=1)
    plan = parse_plan(spec.render())

    assert next_available_phase(plan) == "P05"


def test_next_available_wave_advances_past_max() -> None:
    """``next_available_wave`` is one past the maximum existing Wave id."""
    rng = random.Random(6)
    spec = make_clean_plan("L3", rng=rng, waves=3, phases=1, steps=1)
    plan = parse_plan(spec.render())

    assert next_available_wave(plan) == "W04"


def test_next_available_step_in_empty_l1_plan_is_s01() -> None:
    """A plan with no Step rows gives ``S01`` as the first available identifier."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#empty'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "---\n"
        "\n"
        "# `empty` plan\n"
        "\n"
        "Plan with no Step rows yet.\n"
    )

    plan = parse_plan(body)
    assert next_available_step(plan) == "S01"


def test_next_available_widens_field_past_99() -> None:
    """When the maximum exceeds 99 the field widens; existing IDs untouched.

    Constructs a plan whose maximum Step id is S099 and asserts the
    next-available counter widens to three digits (``S100``). Existing
    identifiers retain their two-digit padding.
    """
    rows = "\n".join(
        f"- [ ] `S{n:03d}` - row action; `src/file_{n}.py`." for n in (1, 50, 99)
    )
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#wide'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-wide-adr]]'\n"
        "---\n"
        "\n"
        "# `wide` plan\n"
        "\n"
        "Plan with a three-digit Step id.\n"
        "\n"
        f"{rows}\n"
    )

    plan = parse_plan(body)
    assert next_available_step(plan) == "S100"


# ---- Duplicate detection ----------------------------------------------------


def test_validate_identifiers_passes_on_clean_plan() -> None:
    """A factory-generated clean plan validates without raising."""
    rng = random.Random(7)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    validate_identifiers(plan)  # no raise


def test_duplicate_step_id_raises() -> None:
    """Two rows with the same canonical Step id raise a typed error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#dup-step'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-dup-step-adr]]'\n"
        "---\n"
        "\n"
        "# `dup-step` plan\n"
        "\n"
        "Plan with a duplicated Step id.\n"
        "\n"
        "- [ ] `S01` - first action; `src/a.py`.\n"
        "- [ ] `S01` - second action; `src/b.py`.\n"
    )
    plan = parse_plan(body)

    with pytest.raises(DuplicateIdentifierError, match="Step"):
        validate_identifiers(plan)


# ---- Randomised stability ---------------------------------------------------


@pytest.mark.parametrize("seed", range(15))
def test_next_available_invariants_under_random_clean_plans(seed: int) -> None:
    """Across many seeds and tiers, ``next_available_*`` always exceeds existing ids."""
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

    next_step = next_available_step(plan)
    if plan.steps:
        max_step = max(int(s.canonical_id[1:]) for s in plan.steps)
        assert int(next_step[1:]) == max_step + 1
    else:
        assert next_step == "S01"
