"""Parametrized and randomised parser tests covering clean, dirty, and
mixed plan documents at every complexity tier.

The suite exercises:

- :func:`parse_plan` round-tripping for clean plans at L1, L2, L3, L4.
- Identifier extraction (canonical leaf vs. display path) across tiers.
- Document-order preservation: the parser yields Steps in source order
  even when canonical identifiers run out of sequence (insert-between
  scenario).
- Tolerance for degraded rows: padding-violations, wrong checkbox
  glyphs, em-dash separators, and lowercase identifiers all fail the
  parser's strict regex and are silently skipped (the parser must not
  crash on any of them).
- Resilience to manually edited documents that drop the trailing period
  on the row-sentence terminator.
- Gap preservation: deleting a Step from a plan leaves a gap; the
  remaining canonical identifiers are unchanged.

Determinism is preserved by seeding ``random.Random`` for every
parametrised case; failures are reproducible from the seed alone.
"""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.parser import (
    EpicIntent,
    Plan,
    PlanParseError,
    parse_plan,
)
from vaultspec_core.tests.plan._factories import (
    PlanSpec,
    StepSpec,
    corrupt_checkbox,
    corrupt_drop_period,
    corrupt_lowercase_id,
    corrupt_padding,
    corrupt_separator,
    inject_gap,
    make_clean_plan,
)

# ---- Clean-plan parametrized matrix ----------------------------------------


@pytest.mark.parametrize(
    ("tier", "waves", "phases", "steps"),
    [
        ("L1", 0, 0, 1),
        ("L1", 0, 0, 7),
        ("L2", 0, 1, 1),
        ("L2", 0, 3, 4),
        ("L3", 1, 1, 1),
        ("L3", 2, 3, 5),
        ("L4", 1, 1, 1),
        ("L4", 3, 2, 4),
    ],
)
def test_clean_plan_parses_at_every_tier(
    tier: str, waves: int, phases: int, steps: int
) -> None:
    """Clean plans at every tier round-trip through the parser without errors."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=waves, phases=phases, steps=steps)

    plan = parse_plan(spec.render())

    assert plan.frontmatter.tier == Tier(tier)
    assert len(plan.steps) == len(spec.steps)
    assert [s.canonical_id for s in plan.steps] == [s.canonical_id for s in spec.steps]


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_step_canonical_ids_are_strictly_monotonic(tier: str) -> None:
    """Canonical Step identifiers (``S##``) increase monotonically across the doc.

    The factory emits Steps in append-order, so a clean plan must
    expose canonical ids in strictly increasing sequence regardless of
    the tier or how the Steps are nested under Phases / Waves.
    """
    rng = random.Random(1)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=3)

    plan = parse_plan(spec.render())

    canonical_numbers = [int(step.canonical_id[1:]) for step in plan.steps]
    assert canonical_numbers == sorted(canonical_numbers)
    assert canonical_numbers == list(
        range(canonical_numbers[0], canonical_numbers[-1] + 1)
    )


@pytest.mark.parametrize(
    ("tier", "expected_path_shape"),
    [
        ("L1", "S{:02d}"),
        ("L2", "P01.S{:02d}"),
        ("L3", "W01.P01.S{:02d}"),
        ("L4", "W01.P01.S{:02d}"),
    ],
)
def test_display_paths_render_tier_conditional_shape(
    tier: str, expected_path_shape: str
) -> None:
    """Display paths follow the tier's ancestor-chain shape from the convention ADR.

    Args:
        tier: Tier under test.
        expected_path_shape: Format string with one ``{}`` placeholder for
            the canonical Step number.
    """
    rng = random.Random(2)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=2)

    plan = parse_plan(spec.render())

    first_step = plan.steps[0]
    expected = expected_path_shape.format(int(first_step.canonical_id[1:]))
    assert first_step.display_path == expected


def test_l4_plan_emits_epic_intent_block() -> None:
    """L4 plans must parse with a non-``None`` Epic intent block."""
    rng = random.Random(3)
    spec = make_clean_plan("L4", rng=rng, waves=2, phases=2, steps=2)

    plan = parse_plan(spec.render())

    assert isinstance(plan.epic_intent, EpicIntent)
    assert plan.epic_intent.text  # non-empty paragraph


@pytest.mark.parametrize("seed", range(8))
def test_phase_intent_paragraph_round_trips_through_parse(seed: int) -> None:
    """Phase intent prose must survive the parse step, not be silently dropped.

    Regression for the silent-data-loss flaw where ``_walk_body`` hard-coded
    ``intent=""`` on every Phase, causing serialiser round-trips to overwrite
    author-written intent prose with the ``TODO:`` placeholder.
    """
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    plan = parse_plan(spec.render())

    assert all(phase.intent for phase in plan.phases)
    for parsed, source in zip(plan.phases, spec.phases, strict=False):
        assert parsed.intent == source.intent.strip()


@pytest.mark.parametrize("seed", range(8))
def test_wave_intent_paragraph_round_trips_through_parse(seed: int) -> None:
    """Wave intent prose must survive the parse step, not be silently dropped."""
    rng = random.Random(seed)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)
    plan = parse_plan(spec.render())

    assert all(wave.intent for wave in plan.waves)
    for parsed, source in zip(plan.waves, spec.waves, strict=False):
        assert parsed.intent == source.intent.strip()


@pytest.mark.parametrize("tier", ["L1", "L2", "L3"])
def test_lower_tiers_have_no_epic_intent(tier: str) -> None:
    """L1, L2, L3 plans never carry an Epic intent block."""
    rng = random.Random(4)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)

    plan = parse_plan(spec.render())

    assert plan.epic_intent is None


# ---- Document-order preservation -------------------------------------------


def test_parser_preserves_document_order_with_out_of_sequence_canonical_ids() -> None:
    """Steps appearing in non-canonical order in the document still parse in
    their document-order positions; canonical identifiers remain unchanged.

    Constructs a hand-written L2 plan where the writer "inserted" S08
    between S02 and S03. The parser must yield the rows in the order
    they appear in the file (S01, S02, S08, S03, ...), not sorted.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#manual-test'\n"
        "date: '2026-05-05'\n"
        "tier: L2\n"
        "related:\n"
        "  - '[[2026-05-05-manual-test-adr]]'\n"
        "---\n"
        "\n"
        "# `manual-test` plan\n"
        "\n"
        "Inserted-step coverage.\n"
        "\n"
        "### Phase `P01` - integration\n"
        "\n"
        "Single Phase exercising the insert-between scenario.\n"
        "\n"
        "- [ ] `P01.S01` - first action; `src/a.py`.\n"
        "- [ ] `P01.S02` - second action; `src/b.py`.\n"
        "- [ ] `P01.S08` - inserted action; `src/c.py`.\n"
        "- [ ] `P01.S03` - third action; `src/d.py`.\n"
    )

    plan = parse_plan(body)

    assert [s.canonical_id for s in plan.steps] == [
        "S01",
        "S02",
        "S08",
        "S03",
    ]


# ---- Degradation tolerance --------------------------------------------------


@pytest.mark.parametrize("seed", range(8))
def test_padding_corruption_skips_only_the_degraded_row(seed: int) -> None:
    """Stripping the leading zero of one Step's identifier removes only that row.

    The convention's two-digit minimum padding is enforced by the
    parser regex. A degraded ``S3`` row fails the regex and is
    silently skipped. All other rows still parse correctly.
    """
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    text = spec.render()

    corrupted = corrupt_padding(text, rng=random.Random(seed + 100))
    plan = parse_plan(corrupted)

    # If the corruption could not find a target (e.g., pre-existing
    # short ID), the plan is identical to the clean plan.
    if corrupted == text:
        assert len(plan.steps) == len(spec.steps)
    else:
        assert len(plan.steps) == len(spec.steps) - 1


@pytest.mark.parametrize("seed", range(8))
def test_checkbox_corruption_skips_only_the_degraded_row(seed: int) -> None:
    """Mangled checkboxes (``[]``, ``[X]``) fail the row regex; row is skipped."""
    rng = random.Random(seed)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=2, steps=2)
    text = spec.render()

    corrupted = corrupt_checkbox(text, rng=random.Random(seed + 200))
    plan = parse_plan(corrupted)

    if corrupted == text:
        assert len(plan.steps) == len(spec.steps)
    else:
        assert len(plan.steps) == len(spec.steps) - 1


@pytest.mark.parametrize("seed", range(8))
def test_separator_corruption_skips_only_the_degraded_row(seed: int) -> None:
    """An em-dash on the row breaks the regex; the row is silently skipped."""
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=2)
    text = spec.render()

    corrupted = corrupt_separator(text, rng=random.Random(seed + 300))
    plan = parse_plan(corrupted)

    if corrupted == text:
        assert len(plan.steps) == len(spec.steps)
    else:
        assert len(plan.steps) == len(spec.steps) - 1


@pytest.mark.parametrize("seed", range(8))
def test_lowercase_identifier_corruption_skips_the_row(seed: int) -> None:
    """Lowercase ``s##`` identifiers fail the uppercase-only regex."""
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    text = spec.render()

    corrupted = corrupt_lowercase_id(text, rng=random.Random(seed + 400))
    plan = parse_plan(corrupted)

    if corrupted == text:
        assert len(plan.steps) == len(spec.steps)
    else:
        assert len(plan.steps) == len(spec.steps) - 1


@pytest.mark.parametrize("seed", range(6))
def test_dropped_trailing_period_still_parses(seed: int) -> None:
    """Removing the trailing period from one row does not break parsing.

    The parser's row contract calls for a trailing period after the
    closing scope backtick, but ``_split_action_and_scope`` strips
    trailing dots defensively. Manually edited rows that lose the
    period still parse; the test asserts that resilience.
    """
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=1, steps=4)
    text = spec.render()

    corrupted = corrupt_drop_period(text, rng=random.Random(seed + 500))
    plan = parse_plan(corrupted)

    assert len(plan.steps) == len(spec.steps)


# ---- Gap preservation -------------------------------------------------------


@pytest.mark.parametrize("seed", range(6))
def test_step_deletion_preserves_surviving_canonical_ids(seed: int) -> None:
    """Deleting one Step removes exactly that Step's canonical id; others unchanged.

    The convention's append-only / no-reuse rule guarantees that
    surviving canonical ids are a strict subset of the pre-deletion
    set with no renumbering. When the deleted Step was internal, a
    visible gap appears in the sequence; when it was terminal, no
    interior gap exists but the maximum id has dropped.
    """
    rng = random.Random(seed)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    pre_ids = {s.canonical_id for s in spec.steps}

    gapped = inject_gap(spec, rng=random.Random(seed + 600))
    post_ids = {s.canonical_id for s in gapped.steps}
    plan = parse_plan(gapped.render())

    parsed_ids = {s.canonical_id for s in plan.steps}

    assert parsed_ids == post_ids
    assert post_ids.issubset(pre_ids)
    assert len(pre_ids) - len(post_ids) == 1
    # No identifier is duplicated in the parsed output.
    assert len(plan.steps) == len(parsed_ids)


# ---- Mixed-degradation stress ----------------------------------------------


@pytest.mark.parametrize("seed", range(12))
def test_mixed_corruptions_never_crash_the_parser(seed: int) -> None:
    """Apply multiple random corruptions to one plan; parser must never crash.

    Verifies the parser's robustness against documents that have been
    edited by hand and accumulated several violations: padding,
    checkbox, separator, period-drop, and lowercase identifiers all
    composed onto the same body.
    """
    rng = random.Random(seed)
    tier = rng.choice(["L1", "L2", "L3", "L4"])
    spec = make_clean_plan(
        tier,
        rng=rng,
        waves=rng.randint(1, 2),
        phases=rng.randint(1, 3),
        steps=rng.randint(2, 4),
    )
    text = spec.render()

    text = corrupt_padding(text, rng=random.Random(seed + 11))
    text = corrupt_checkbox(text, rng=random.Random(seed + 22))
    text = corrupt_separator(text, rng=random.Random(seed + 33))
    text = corrupt_drop_period(text, rng=random.Random(seed + 44))
    text = corrupt_lowercase_id(text, rng=random.Random(seed + 55))

    plan = parse_plan(text)

    assert isinstance(plan, Plan)
    assert plan.frontmatter.tier == Tier(tier)
    # Whatever survived must still expose monotonic canonical ids.
    canonical_numbers = [int(s.canonical_id[1:]) for s in plan.steps]
    assert canonical_numbers == sorted(canonical_numbers)


# ---- Malformed-row error path ----------------------------------------------


def test_step_row_without_semicolon_separator_raises() -> None:
    """A row missing the ``;`` between action and scope is a contract violation.

    The parser raises :class:`PlanParseError` so callers can surface a
    targeted diagnostic instead of producing a half-parsed Step.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#error-test'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-error-test-adr]]'\n"
        "---\n"
        "\n"
        "# `error-test` plan\n"
        "\n"
        "Plan with one malformed row.\n"
        "\n"
        "- [ ] `S01` - missing-separator action and scope without semicolon.\n"
    )

    with pytest.raises(PlanParseError, match="';'"):
        parse_plan(body)


# ---- Sanity: rendered factory text contains every spec'd Step ---------------


@pytest.mark.parametrize(
    ("tier", "waves", "phases", "steps"),
    [
        ("L1", 0, 0, 5),
        ("L2", 0, 2, 3),
        ("L3", 2, 2, 2),
        ("L4", 1, 2, 3),
    ],
)
def test_factory_render_contains_every_step_canonical_id(
    tier: str, waves: int, phases: int, steps: int
) -> None:
    """Every Step the factory specs must appear in the rendered Markdown.

    Sanity check that the test fixtures themselves are not silently
    dropping rows. A failure here is a defect in the factory module
    rather than the parser.
    """
    rng = random.Random(7)
    spec = make_clean_plan(tier, rng=rng, waves=waves, phases=phases, steps=steps)
    text = spec.render()

    for step in spec.steps:
        assert f"`{step.display_path}`" in text


def _step_canonical_count(spec: PlanSpec) -> int:
    """Count canonical Step identifiers in the spec for assertion reuse."""
    return len({s.canonical_id for s in spec.steps})


def _step_action_summary(step: StepSpec) -> str:
    """Render a Step's action + scope for diagnostic messages in failures."""
    return f"{step.action}; `{step.scope}`"
