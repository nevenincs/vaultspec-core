"""Tests for tier-conditional display-path computation."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.display_path import (
    compute_display_paths,
    phase_display_path,
    step_display_path,
    wave_display_path,
)
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Direct path-builder helpers --------------------------------------------


@pytest.mark.parametrize(
    ("step_id", "phase_id", "wave_id", "expected"),
    [
        ("S03", None, None, "S03"),
        ("S03", "P02", None, "P02.S03"),
        ("S03", "P02", "W01", "W01.P02.S03"),
        ("S15", "P09", "W04", "W04.P09.S15"),
    ],
)
def test_step_display_path_assembles_ancestor_chain(
    step_id: str, phase_id: str | None, wave_id: str | None, expected: str
) -> None:
    """Step paths render every present ancestor segment, in order."""
    assert (
        step_display_path(step_id=step_id, phase_id=phase_id, wave_id=wave_id)
        == expected
    )


def test_step_display_path_rejects_wave_without_phase() -> None:
    """A Wave parent without a Phase parent is not a legal Step ancestry."""
    with pytest.raises(ValueError, match="phase_id"):
        step_display_path(step_id="S01", wave_id="W01")


@pytest.mark.parametrize(
    ("phase_id", "wave_id", "expected"),
    [
        ("P01", None, "P01"),
        ("P03", "W02", "W02.P03"),
    ],
)
def test_phase_display_path_assembles_chain(
    phase_id: str, wave_id: str | None, expected: str
) -> None:
    """Phase paths concatenate the optional Wave ancestor with the canonical id."""
    assert phase_display_path(phase_id=phase_id, wave_id=wave_id) == expected


def test_wave_display_path_is_canonical_id() -> None:
    """Wave headings render their canonical id alone (Epic frame implicit)."""
    assert wave_display_path(wave_id="W01") == "W01"


# ---- compute_display_paths against parsed Plans ------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_compute_display_paths_matches_parsed_step_paths(tier: str) -> None:
    """Recomputed display paths match the values the parser already extracted.

    For a clean plan the round-trip is byte-for-byte; this test
    exercises the recomputation logic against every tier.
    """
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    table = compute_display_paths(plan)

    for step in plan.steps:
        assert table.steps[step.canonical_id] == step.display_path


def test_compute_display_paths_l3_includes_wave_segment() -> None:
    """L3 step paths carry a ``W##`` prefix; L1 step paths do not."""
    rng = random.Random(1)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=1, steps=1)
    plan = parse_plan(spec.render())

    table = compute_display_paths(plan)
    only_step_id = next(iter(table.steps))

    assert table.steps[only_step_id].count(".") == 2
    assert table.steps[only_step_id].startswith("W")


def test_compute_display_paths_l1_step_paths_have_no_dots() -> None:
    """At L1 every Step path equals the canonical id (no ancestor segments)."""
    rng = random.Random(2)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    plan = parse_plan(spec.render())

    table = compute_display_paths(plan)

    for canonical_id, display_path in table.steps.items():
        assert canonical_id == display_path
        assert "." not in display_path


def test_compute_display_paths_l4_phase_headings_carry_wave_prefix() -> None:
    """L4 Phase headings render ``W##.P##``; the Epic frame is implicit."""
    rng = random.Random(3)
    spec = make_clean_plan("L4", rng=rng, waves=2, phases=2, steps=1)
    plan = parse_plan(spec.render())

    table = compute_display_paths(plan)

    for phase_id, phase_path in table.phases.items():
        assert phase_path.startswith("W")
        assert phase_path.endswith(phase_id)
        assert phase_path.count(".") == 1


def test_compute_display_paths_l2_phase_headings_have_no_wave_prefix() -> None:
    """L2 Phase headings render the bare canonical id."""
    rng = random.Random(4)
    spec = make_clean_plan("L2", rng=rng, phases=3, steps=1)
    plan = parse_plan(spec.render())

    table = compute_display_paths(plan)

    assert all(not path.startswith("W") for path in table.phases.values())


# ---- Stability under randomised parameters ----------------------------------


@pytest.mark.parametrize("seed", range(12))
def test_compute_display_paths_is_idempotent_against_parsed_plans(seed: int) -> None:
    """Running compute twice yields the same table; computation is pure."""
    rng = random.Random(seed)
    tier = rng.choice(["L1", "L2", "L3", "L4"])
    spec = make_clean_plan(
        tier,
        rng=rng,
        waves=rng.randint(1, 2),
        phases=rng.randint(1, 3),
        steps=rng.randint(1, 3),
    )
    plan = parse_plan(spec.render())

    first = compute_display_paths(plan)
    second = compute_display_paths(plan)

    assert first == second
