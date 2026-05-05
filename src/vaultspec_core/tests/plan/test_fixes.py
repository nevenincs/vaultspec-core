"""Tests for the four autofix transformations and the harness."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.fixes import apply_all_fixes
from vaultspec_core.plan.fixes.checkbox_fix import fix_checkbox_spacing
from vaultspec_core.plan.fixes.separator_fix import fix_separator
from vaultspec_core.plan.fixes.whitespace_fix import fix_trailing_whitespace
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan


def test_checkbox_fix_normalises_no_space_form() -> None:
    """``- []`` becomes ``- [ ]``."""
    text = "- [] action; `src/a.py`.\n"

    fixed = fix_checkbox_spacing(text)

    assert fixed == "- [ ] action; `src/a.py`.\n"


def test_checkbox_fix_normalises_uppercase_x() -> None:
    """``- [X]`` becomes ``- [x]``."""
    text = "- [X] `S01` - action; `src/a.py`.\n"

    fixed = fix_checkbox_spacing(text)

    assert fixed == "- [x] `S01` - action; `src/a.py`.\n"


def test_checkbox_fix_is_idempotent() -> None:
    """A second run of the fix produces no further changes."""
    text = "- [] one\n- [X] two\n- [ ] three\n"

    once = fix_checkbox_spacing(text)
    twice = fix_checkbox_spacing(once)

    assert once == twice


def test_separator_fix_replaces_em_dash_with_ascii_hyphen() -> None:
    """An em-dash becomes ``' - '`` (single spaces)."""
    text = "before \N{EM DASH} after"

    fixed = fix_separator(text)

    assert fixed == "before - after"


def test_separator_fix_replaces_en_dash() -> None:
    """An en-dash becomes ``' - '`` likewise."""
    text = "before\N{EN DASH}after"

    fixed = fix_separator(text)

    assert fixed == "before - after"


def test_separator_fix_is_idempotent() -> None:
    """A second run on already-canonical text yields no further changes."""
    text = "alpha - beta - gamma"

    once = fix_separator(text)
    twice = fix_separator(once)

    assert once == twice
    assert once == text


def test_whitespace_fix_strips_trailing_spaces() -> None:
    """Trailing spaces and tabs are removed from each line."""
    text = "first line   \nsecond line\t\nthird line\n"

    fixed = fix_trailing_whitespace(text)

    assert fixed == "first line\nsecond line\nthird line\n"


def test_whitespace_fix_preserves_final_newline_when_present() -> None:
    """A trailing newline survives the fix."""
    assert fix_trailing_whitespace("line\n") == "line\n"


def test_whitespace_fix_omits_final_newline_when_absent() -> None:
    """Text without a trailing newline still has none after the fix."""
    assert fix_trailing_whitespace("line") == "line"


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_apply_all_fixes_round_trips_clean_plan(tier: str) -> None:
    """A clean plan survives the harness untouched and re-parses cleanly."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=2)
    text = spec.render()

    fixed = apply_all_fixes(text)
    re_parsed = parse_plan(fixed)

    assert [s.canonical_id for s in re_parsed.steps] == [
        s.canonical_id for s in spec.steps
    ]


def test_apply_all_fixes_repairs_em_dash_separator() -> None:
    """Composing all fixes resolves an em-dash row into a parseable Step.

    Targets a specific Step row's separator (after the closing
    backtick of the display path) so the corruption does not also
    affect the YAML frontmatter list-item leaders.
    """
    rng = random.Random(1)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    text = spec.render().replace("` - ", "` \N{EM DASH} ", 1)

    fixed = apply_all_fixes(text)
    plan = parse_plan(fixed)

    assert len(plan.steps) == 2


def test_apply_all_fixes_is_idempotent_under_random_seeds() -> None:
    """Applying the harness twice yields the same text on the second run."""
    rng = random.Random(2)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=2, steps=2)

    once = apply_all_fixes(spec.render())
    twice = apply_all_fixes(once)

    assert once == twice
