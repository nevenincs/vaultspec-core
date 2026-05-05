"""Hierarchy-correspondence detection rule (``PLAN010``).

Verifies the declared ``tier:`` matches the document's heading shape:

- ``L1``: no Wave heading, no Phase heading, no Epic intent block.
- ``L2``: Phase headings only; no Waves; no Epic intent.
- ``L3``: Wave + Phase headings; no Epic intent.
- ``L4``: Epic intent + Wave + Phase headings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.plan.frontmatter import Tier

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_hierarchy"]


def check_hierarchy(plan: Plan) -> list[Finding]:
    """Detect tier-vs-structure mismatches."""
    findings: list[Finding] = []
    tier = plan.frontmatter.tier

    if tier is Tier.L1:
        if plan.waves:
            findings.append(_mk("L1 plan must not contain Wave headings"))
        if plan.phases:
            findings.append(_mk("L1 plan must not contain Phase headings"))
        if plan.epic_intent is not None:
            findings.append(_mk("L1 plan must not contain an Epic intent block"))

    elif tier is Tier.L2:
        if plan.waves:
            findings.append(_mk("L2 plan must not contain Wave headings"))
        if plan.epic_intent is not None:
            findings.append(_mk("L2 plan must not contain an Epic intent block"))
        if not plan.phases:
            findings.append(_mk("L2 plan must contain at least one Phase heading"))

    elif tier is Tier.L3:
        if plan.epic_intent is not None:
            findings.append(_mk("L3 plan must not contain an Epic intent block"))
        if not plan.waves:
            findings.append(_mk("L3 plan must contain at least one Wave heading"))

    elif tier is Tier.L4:
        if plan.epic_intent is None:
            findings.append(_mk("L4 plan must contain an Epic intent block"))
        if not plan.waves:
            findings.append(_mk("L4 plan must contain at least one Wave heading"))

    return findings


def _mk(message: str) -> Finding:
    """Build a hierarchy-correspondence Finding with the canonical code."""
    return Finding(
        code="PLAN010",
        severity=Severity.ERROR,
        message=message,
        fix_hint=(
            "Reconcile the 'tier:' frontmatter field with the document's "
            "heading structure per the convention ADR's tier-driven "
            "structure rules."
        ),
        autofixable=False,
    )
