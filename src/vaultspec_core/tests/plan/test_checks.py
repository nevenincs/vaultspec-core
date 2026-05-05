"""Tests for the seven detection rules and the ``collect_all`` harness."""

from __future__ import annotations

import random

import pytest

from vaultspec_core.plan.checks import Severity, collect_all, has_errors
from vaultspec_core.plan.checks.frontmatter_check import check_frontmatter
from vaultspec_core.plan.checks.hierarchy_check import check_hierarchy
from vaultspec_core.plan.checks.identifiers_check import check_identifiers
from vaultspec_core.plan.checks.row_contract_check import check_row_contract
from vaultspec_core.plan.checks.separator_check import check_separator
from vaultspec_core.plan.checks.vocabulary_check import check_vocabulary
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

# ---- Clean plans produce zero errors ----------------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_clean_plan_has_no_error_findings(tier: str) -> None:
    """A factory-clean plan emits no error-level findings."""
    rng = random.Random(0)
    spec = make_clean_plan(tier, rng=rng, waves=2, phases=2, steps=2)
    text = spec.render()
    plan = parse_plan(text)

    findings = collect_all(plan, text)

    assert not has_errors(findings), [
        (f.code, f.severity.value, f.message) for f in findings
    ]


# ---- Frontmatter rule -------------------------------------------------------


def test_frontmatter_check_warns_on_missing_tier() -> None:
    """Legacy plans without ``tier:`` emit a PLAN001 warning."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#legacy'\n"
        "date: '2026-05-05'\n"
        "related:\n"
        "  - '[[2026-05-05-legacy-adr]]'\n"
        "---\n"
        "\n"
        "# `legacy` plan\n"
        "\n"
        "Legacy.\n"
        "\n"
        "- [ ] `S01` - first action; `src/a.py`.\n"
    )
    plan = parse_plan(body)

    findings = check_frontmatter(plan)

    codes = [finding.code for finding in findings]
    assert "PLAN001" in codes


# ---- Hierarchy rule ---------------------------------------------------------


def test_hierarchy_check_errors_when_l1_has_phase() -> None:
    """An L1 plan with a Phase heading raises a PLAN010 error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-l1'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-bad-l1-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-l1` plan\n"
        "\n"
        "Plan that violates L1 by including a Phase heading.\n"
        "\n"
        "### Phase `P01` - illegal phase\n"
        "\n"
        "Phase intent.\n"
        "\n"
        "- [ ] `P01.S01` - first action; `src/a.py`.\n"
    )
    plan = parse_plan(body)

    findings = check_hierarchy(plan)

    assert any(finding.code == "PLAN010" for finding in findings)


# ---- Identifier-hygiene rule ------------------------------------------------


def test_identifier_check_flags_duplicate_step_id() -> None:
    """Two rows with the same Step canonical id raise a PLAN021 error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#dup'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-dup-adr]]'\n"
        "---\n"
        "\n"
        "# `dup` plan\n"
        "\n"
        "Plan with a duplicated Step id.\n"
        "\n"
        "- [ ] `S01` - first; `src/a.py`.\n"
        "- [ ] `S01` - duplicate; `src/b.py`.\n"
    )
    plan = parse_plan(body)

    findings = check_identifiers(plan, body)

    assert any(finding.code == "PLAN021" for finding in findings)


def test_identifier_check_flags_underpadded_phase_heading() -> None:
    """A single-digit Phase heading id raises PLAN020 even when the parser drops it.

    Regression for the H4 finding: the parser regex requires ``\\d{2,}`` so
    ``### Phase `P1` - title`` is silently dropped from the model. The
    identifier check must scan the raw text to surface the violation.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#padding'\n"
        "date: '2026-05-05'\n"
        "tier: L2\n"
        "related:\n"
        "  - '[[2026-05-05-padding-adr]]'\n"
        "---\n"
        "\n"
        "# `padding` plan\n"
        "\n"
        "Plan with a single-digit Phase id.\n"
        "\n"
        "### Phase `P1` - illegal padding\n"
        "\n"
        "Phase intent.\n"
        "\n"
        "- [ ] `P01.S01` - first; `src/a.py`.\n"
    )
    plan = parse_plan(body)

    findings = check_identifiers(plan, body)

    assert any(
        finding.code == "PLAN020" and "P1" in finding.message for finding in findings
    )


def test_vocabulary_check_flags_epic_intent_with_wrong_noun() -> None:
    """``## Initiative intent`` raises PLAN050 even without a backticked id.

    Regression for the H3 finding: the original heading regex required a
    backtick after the noun, so the bare ``## Initiative intent`` shape was
    invisible to the rule. The check now matches the bare ``intent``
    structural position too.
    """
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-epic'\n"
        "date: '2026-05-05'\n"
        "tier: L4\n"
        "related:\n"
        "  - '[[2026-05-05-bad-epic-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-epic` plan\n"
        "\n"
        "## Initiative intent\n"
        "\n"
        "Some prose for the (mis-named) Epic block.\n"
        "\n"
        "## Wave `W01` - first wave\n"
        "\n"
        "Wave intent.\n"
        "\n"
        "### Phase `W01.P01` - first phase\n"
        "\n"
        "Phase intent.\n"
        "\n"
        "- [ ] `W01.P01.S01` - first; `src/a.py`.\n"
    )
    canonical = body.replace("## Initiative intent", "## Epic intent")

    findings = check_vocabulary(parse_plan(canonical), body)

    assert any(
        finding.code == "PLAN050" and "Initiative" in finding.message
        for finding in findings
    )


# ---- Row-contract rule ------------------------------------------------------


def test_row_contract_check_flags_missing_semicolon() -> None:
    """A row missing the ``;`` separator emits a PLAN040 error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-row'\n"
        "date: '2026-05-05'\n"
        "tier: L1\n"
        "related:\n"
        "  - '[[2026-05-05-bad-row-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-row` plan\n"
        "\n"
        "Plan whose row lacks the ';' separator.\n"
    )
    # Construct a plan without parser-rejected rows to satisfy the
    # parser's grammar, then append a malformed line as raw text only.
    text = body + "- [ ] `S01` - missing-separator action and scope.\n"

    findings = check_row_contract(parse_plan(body), text)

    assert any(finding.code == "PLAN040" for finding in findings)


# ---- Vocabulary rule --------------------------------------------------------


def test_vocabulary_check_flags_non_canonical_heading_noun() -> None:
    """A heading with a non-canonical structural noun emits a PLAN050 error."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#bad-vocab'\n"
        "date: '2026-05-05'\n"
        "tier: L2\n"
        "related:\n"
        "  - '[[2026-05-05-bad-vocab-adr]]'\n"
        "---\n"
        "\n"
        "# `bad-vocab` plan\n"
        "\n"
        "Plan with a non-canonical structural heading noun.\n"
        "\n"
        "### Sprint `P01` - non-canonical heading\n"
        "\n"
        "Phase intent.\n"
        "\n"
        "- [ ] `P01.S01` - first; `src/a.py`.\n"
    )
    # Parse a minimal valid plan so check_vocabulary has a Plan; the
    # vocabulary scan operates on raw text alone for the assertion.
    minimal = body.replace(
        "### Sprint `P01` - non-canonical heading",
        "### Phase `P01` - non-canonical heading",
    )

    findings = check_vocabulary(parse_plan(minimal), body)

    assert any(finding.code == "PLAN050" for finding in findings)


# ---- Separator rule ---------------------------------------------------------


def test_separator_check_flags_em_dash_in_source() -> None:
    """An em-dash anywhere in source text emits a PLAN060 error."""
    bad_text = "Plan body with an em-dash \N{EM DASH} that violates the convention.\n"

    findings = check_separator(bad_text)

    assert any(finding.code == "PLAN060" for finding in findings)


# ---- Harness composition ----------------------------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_collect_all_runs_every_rule_without_raising(tier: str) -> None:
    """The harness composes the seven rules; on a clean plan it returns clean."""
    rng = random.Random(5)
    spec = make_clean_plan(tier, rng=rng, waves=1, phases=1, steps=1)
    text = spec.render()
    plan = parse_plan(text)

    findings = collect_all(plan, text)

    assert all(isinstance(f.code, str) for f in findings)
    assert all(isinstance(f.severity, Severity) for f in findings)
