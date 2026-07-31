"""Parametrized tests for plan-frontmatter parsing and the legacy default.

Covers:

- Every valid ``tier`` value (``L1``-``L4``) round-trips through the parser.
- Plans missing the ``tier`` field default to ``L2`` and report
  ``legacy_tier_default=True`` so callers can apply the migration hint.
- Invalid ``tier`` scalars (lowercase, unknown enum, non-string) raise
  :class:`PlanFrontmatterError`.
- ``related`` round-trips when present and tolerates absence (empty list).
- Missing or malformed ``tags`` (no directory tag, no feature tag) raise.
- An unquoted ``date:`` scalar - which YAML hands back as a
  :class:`datetime.date` - is normalised to its canonical ``yyyy-mm-dd``
  string instead of locking the document out of every plan verb.
- Mixed degradations across many seeds never crash the parser; either
  the document parses or a targeted error is raised.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.plan.frontmatter import (
    PlanFrontmatterError,
    Tier,
    parse_plan_frontmatter,
)
from vaultspec_core.tests.plan._factories import make_clean_plan

if TYPE_CHECKING:
    from pathlib import Path

# ---- Valid tier values -----------------------------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_valid_tier_values_parse_and_do_not_flag_legacy(tier: str) -> None:
    """Each canonical tier value parses cleanly with no legacy-default flag."""
    rng = random.Random(10)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)

    fm = parse_plan_frontmatter(spec.render())

    assert fm.tier == Tier(tier)
    assert fm.legacy_tier_default is False


def test_missing_tier_defaults_to_l2_with_legacy_flag() -> None:
    """A plan without the ``tier`` field is treated as ``L2`` (legacy default).

    The convention ADR's Frontmatter contract pins the migration rule:
    pre-existing plans without the field default to ``L2`` and the
    writer adds the field on first edit. The parser must surface a
    flag so callers can emit the migration warning.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#legacy-test'\n"
        "date: '2026-05-05'\n"
        "related:\n"
        "  - '[[2026-05-05-legacy-test-adr]]'\n"
        "---\n"
        "\n"
        "# `legacy-test` plan\n"
        "\n"
        "Pre-existing plan without a tier field.\n"
    )

    fm = parse_plan_frontmatter(body)

    assert fm.tier == Tier.L2
    assert fm.legacy_tier_default is True


# ---- Invalid tier values ---------------------------------------------------


@pytest.mark.parametrize(
    "bad_tier",
    [
        "l1",  # lowercase
        "L0",  # below valid range
        "L5",  # above valid range
        "Tier1",  # unrelated
        "  L2  ",  # padded whitespace
    ],
)
def test_invalid_tier_string_raises(bad_tier: str) -> None:
    """Non-canonical ``tier`` strings raise :class:`PlanFrontmatterError`."""
    body = _frontmatter_with_tier_value(repr(bad_tier))

    with pytest.raises(PlanFrontmatterError, match="tier"):
        parse_plan_frontmatter(body)


def test_non_string_tier_raises() -> None:
    """A numeric or list ``tier`` value raises a typed parse error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#numeric-tier'\n"
        "date: '2026-05-05'\n"
        "tier: 2\n"
        "related:\n"
        "  - '[[2026-05-05-numeric-tier-adr]]'\n"
        "---\n"
        "\n"
        "# `numeric-tier` plan\n"
        "\n"
        "Plan with a numeric tier scalar.\n"
    )

    with pytest.raises(PlanFrontmatterError, match="tier"):
        parse_plan_frontmatter(body)


# ---- Required tag enforcement ----------------------------------------------


def test_missing_directory_tag_raises() -> None:
    """A plan without ``#plan`` in its tag list is rejected."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#missing-directory'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related: []\n"
        "---\n"
        "\n"
        "# `missing-directory` plan\n"
        "\n"
        "Plan whose tag list lacks the directory tag.\n"
    )

    with pytest.raises(PlanFrontmatterError, match="#plan"):
        parse_plan_frontmatter(body)


def test_missing_feature_tag_raises() -> None:
    """A plan with only the directory tag (no feature tag) is rejected."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related: []\n"
        "---\n"
        "\n"
        "# `no-feature` plan\n"
        "\n"
        "Plan with no feature tag.\n"
    )

    with pytest.raises(PlanFrontmatterError, match="feature"):
        parse_plan_frontmatter(body)


# ---- Related-field handling -------------------------------------------------


def test_related_round_trips_quoted_wikilinks() -> None:
    """The ``related`` list preserves quoted wiki-link entries verbatim."""
    rng = random.Random(11)
    spec = make_clean_plan("L1", rng=rng, steps=1)
    fm = parse_plan_frontmatter(spec.render())

    assert fm.related == ["[[2026-05-05-test-feature-adr]]"]


def test_missing_related_field_yields_empty_list() -> None:
    """Plans without a ``related`` field parse with an empty related list.

    Empty-plan scaffolds may omit ``related`` until the first Step is
    added per the convention's Frontmatter contract.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#scaffold'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "---\n"
        "\n"
        "# `scaffold` plan\n"
        "\n"
        "Empty-plan scaffold.\n"
    )

    fm = parse_plan_frontmatter(body)

    assert fm.related == []


def test_related_must_be_a_yaml_list_not_a_scalar() -> None:
    """A scalar ``related`` field violates the Frontmatter contract."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-related'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related: '[[2026-05-05-bad-related-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-related` plan\n"
        "\n"
        "Plan whose related is a string instead of a list.\n"
    )

    with pytest.raises(PlanFrontmatterError, match="related"):
        parse_plan_frontmatter(body)


# ---- Date-field handling ----------------------------------------------------


@pytest.mark.parametrize(
    ("date_literal", "expected"),
    [
        ("2026-03-05", "2026-03-05"),  # YAML yields a datetime.date
        ("2026-04-12", "2026-04-12"),
        ("2026-03-16 09:30:00", "2026-03-16"),  # YAML yields a datetime.datetime
        ("2026-03-16T09:30:00Z", "2026-03-16"),
    ],
)
def test_unquoted_date_scalar_normalises_to_canonical_string(
    date_literal: str,
    expected: str,
) -> None:
    """An unquoted ``date:`` parses to its canonical ``yyyy-mm-dd`` string.

    PyYAML resolves an unquoted ``yyyy-mm-dd`` scalar to a
    :class:`datetime.date` (and a timestamp to a
    :class:`datetime.datetime`), which is the first input
    :func:`~vaultspec_core.vaultcore.models.parse_lenient_date` is
    written to absorb. Missing the quotes is an ordinary authoring slip,
    so the plan parser normalises rather than rejecting the document.
    """
    fm = parse_plan_frontmatter(_frontmatter_with_date_value(date_literal))

    assert fm.date == expected


def test_unquoted_date_parses_from_a_real_file_on_disk(tmp_path: Path) -> None:
    """The path-input route absorbs an unquoted ``date:`` just as the text route does.

    Every plan verb reaches the parser through a real document path, so
    the reachability guarantee has to hold for a file on disk and not
    only for in-memory text.
    """
    plan_path = tmp_path / "2026-03-05-unquoted-date-plan.md"
    plan_path.write_text(_frontmatter_with_date_value("2026-03-05"), encoding="utf-8")

    fm = parse_plan_frontmatter(plan_path)

    assert fm.date == "2026-03-05"
    assert fm.tier == Tier.L1


def test_quoted_canonical_date_round_trips_unchanged() -> None:
    """A canonical quoted ``date:`` is preserved verbatim."""
    fm = parse_plan_frontmatter(_frontmatter_with_date_value("'2026-05-05'"))

    assert fm.date == "2026-05-05"


def test_missing_date_field_yields_empty_string() -> None:
    """A plan without a ``date:`` field parses with an empty date."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#no-date'\n"
        "tier: L1\n"
        "---\n"
        "\n"
        "# `no-date` plan\n"
        "\n"
        "Plan with no date field.\n"
    )

    fm = parse_plan_frontmatter(body)

    assert fm.date == ""


@pytest.mark.parametrize("bad_date", ["42", "[2026-03-05]", "{y: 2026}"])
def test_non_date_scalar_raises(bad_date: str) -> None:
    """Values that are neither a string nor a date are still rejected.

    Coercion is scoped to the date-typed scalars YAML produces from an
    unquoted stamp; a number, list, or mapping remains a typed parse
    error rather than being guessed at.
    """
    with pytest.raises(PlanFrontmatterError, match="date"):
        parse_plan_frontmatter(_frontmatter_with_date_value(bad_date))


# ---- Randomised stability ---------------------------------------------------


@pytest.mark.parametrize("seed", range(20))
def test_random_clean_plan_frontmatter_round_trips(seed: int) -> None:
    """Twenty random seeds, four tiers, varied container counts: parser is stable.

    The randomised matrix exercises every tier with random container
    counts; every clean plan must parse without raising.
    """
    rng = random.Random(seed)
    tier = rng.choice(["L1", "L2", "L3", "L4"])
    spec = make_clean_plan(
        tier,
        rng=rng,
        waves=rng.randint(1, 3),
        phases=rng.randint(1, 3),
        steps=rng.randint(1, 5),
    )

    fm = parse_plan_frontmatter(spec.render())

    assert fm.tier == Tier(tier)
    assert fm.legacy_tier_default is False
    assert fm.related, "factory always emits at least one authorising document"
    assert "#plan" in fm.tags
    assert any(
        tag.startswith("#") and tag != "#plan" and tag not in _DIRECTORY_TAGS
        for tag in fm.tags
    ), "factory must emit a feature tag"


def _frontmatter_with_date_value(date_literal: str) -> str:
    """Render an otherwise-clean plan whose ``date:`` is the given YAML literal."""
    return (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#date-shapes'\n"
        f"date: {date_literal}\n"
        "modified: '2026-06-13'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-03-05-date-shapes-adr]]'\n"
        "---\n"
        "\n"
        "# `date-shapes` plan\n"
        "\n"
        "- [ ] `S01` - do the work; `src/a.py`.\n"
    )


def _frontmatter_with_tier_value(tier_literal: str) -> str:
    """Render an otherwise-clean plan whose ``tier`` is the given YAML literal."""
    return (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-tier'\n"
        "date: '2026-05-05'\n"
        f"tier: {tier_literal}\n"
        "related:\n"
        "  - '[[2026-05-05-bad-tier-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-tier` plan\n"
        "\n"
        "Plan with an invalid tier scalar.\n"
    )


_DIRECTORY_TAGS = frozenset(
    {"#adr", "#audit", "#exec", "#index", "#plan", "#reference", "#research"},
)
