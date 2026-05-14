"""Frontmatter detection rule (``PLAN001``-``PLAN003``).

Validates frontmatter contract from the convention ADR's
*Frontmatter contract* section:

- ``PLAN001 missing-tier`` (warning): plan lacks a ``tier:`` field;
  the parser applied the legacy ``L2`` default. Auto-fixable by
  ``vaultspec-core vault plan check --fix`` (writes the field on first edit).
- ``PLAN002 missing-related`` (error): plan contains at least one
  Step row but the ``related:`` frontmatter field is absent or empty.
- ``PLAN003 stub-epic-intent`` (warning): an L4 plan's Epic intent
  paragraph contains a ``TODO:`` sentinel left behind by ``tier
  promote --to L4`` when the writer did not supply ``--epic-intent``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.plan.frontmatter import Tier

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_frontmatter"]


def check_frontmatter(plan: Plan) -> list[Finding]:
    """Run the three frontmatter detection rules against ``plan``."""
    findings: list[Finding] = []

    if plan.frontmatter.legacy_tier_default:
        findings.append(
            Finding(
                code="PLAN001",
                severity=Severity.WARNING,
                message=(
                    "Plan is missing the 'tier:' frontmatter field; "
                    "treated as L2 by default."
                ),
                line_number=1,
                fix_hint=(
                    "Add 'tier: L1', 'L2', 'L3', or 'L4' to the YAML "
                    "frontmatter per the convention ADR's Frontmatter "
                    "contract section."
                ),
                autofixable=True,
            ),
        )

    if plan.steps and not plan.frontmatter.related:
        findings.append(
            Finding(
                code="PLAN002",
                severity=Severity.ERROR,
                message=(
                    "Plan contains Step rows but the 'related:' "
                    "frontmatter field is empty; authorising documents "
                    "(ADR, research, reference, prior plan) MUST be "
                    "listed for every non-trivial plan."
                ),
                line_number=1,
                fix_hint=(
                    "Add at least one quoted wiki-link to the 'related:' "
                    "list (e.g., '- [[2026-...-feature-adr]]')."
                ),
                autofixable=False,
            ),
        )

    if (
        plan.frontmatter.tier is Tier.L4
        and plan.epic_intent is not None
        and "TODO:" in plan.epic_intent.text
    ):
        findings.append(
            Finding(
                code="PLAN003",
                severity=Severity.WARNING,
                message=(
                    "L4 Epic intent paragraph contains a 'TODO:' sentinel "
                    "left by 'tier promote --to L4' without an explicit "
                    "--epic-intent argument."
                ),
                line_number=plan.epic_intent.line_number,
                fix_hint=(
                    "Edit the '## Epic intent' block to declare the "
                    "external project-management association (milestone, "
                    "project board, or roadmap entry) per the convention "
                    "ADR."
                ),
                autofixable=False,
            ),
        )

    return findings
