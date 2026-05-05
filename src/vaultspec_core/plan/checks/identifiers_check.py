"""Identifier-hygiene detection rule (``PLAN020``-``PLAN022``).

Validates canonical identifiers against the convention ADR's
*Identifiers and addressing* section:

- ``PLAN020 padding-violation`` (error): an identifier's numeric tail
  is shorter than the two-digit minimum.
- ``PLAN021 duplicate-identifier`` (error): the same canonical
  identifier appears on multiple rows or container headings.
- ``PLAN022 non-monotonic-id`` (warning): canonical identifiers are
  not strictly monotonically increasing in document order. This is
  not a hard violation (the writer may have inserted a Step between
  existing rows on purpose, leaving a higher canonical id earlier in
  the document) but the warning surfaces for review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.plan.identifiers import extract_inventory

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_identifiers"]


def check_identifiers(plan: Plan) -> list[Finding]:
    """Detect padding violations, duplicates, and non-monotonic ids."""
    inventory = extract_inventory(plan)
    findings: list[Finding] = []

    for violation in inventory.padding_violations:
        findings.append(
            Finding(
                code="PLAN020",
                severity=Severity.ERROR,
                message=(
                    f"{violation.kind}-identifier '{violation.value}' "
                    "violates the two-digit minimum padding rule."
                ),
                line_number=violation.line_number,
                fix_hint=(
                    "Pad the numeric tail to at least two digits; the "
                    "convention forbids retroactively re-padding existing "
                    "identifiers, so this typically requires removing the "
                    "violating row and re-creating it via 'vault plan "
                    "step add'."
                ),
                autofixable=False,
            ),
        )

    findings.extend(
        _detect_duplicates(inventory.steps, kind="Step", line_lookup=plan.steps),
    )
    findings.extend(
        _detect_duplicates(inventory.phases, kind="Phase", line_lookup=plan.phases),
    )
    findings.extend(
        _detect_duplicates(inventory.waves, kind="Wave", line_lookup=plan.waves),
    )

    findings.extend(_detect_non_monotonic(inventory.steps, kind="Step"))

    return findings


def _detect_duplicates(
    identifiers: list[str],
    *,
    kind: str,
    line_lookup: list,
) -> list[Finding]:
    """Yield one Finding per duplicate canonical identifier."""
    counts: dict[str, list[int]] = {}
    for index, identifier in enumerate(identifiers):
        counts.setdefault(identifier, []).append(index)
    findings: list[Finding] = []
    for identifier, occurrences in counts.items():
        if len(occurrences) <= 1:
            continue
        first_line = line_lookup[occurrences[0]].line_number
        findings.append(
            Finding(
                code="PLAN021",
                severity=Severity.ERROR,
                message=(
                    f"{kind} canonical identifier '{identifier}' appears "
                    f"{len(occurrences)} times in document order."
                ),
                line_number=first_line,
                fix_hint=(
                    "Remove or rename the duplicate occurrences; the "
                    "convention forbids re-using retired identifiers."
                ),
                autofixable=False,
            ),
        )
    return findings


def _detect_non_monotonic(identifiers: list[str], *, kind: str) -> list[Finding]:
    """Yield one Finding when identifiers are not strictly increasing."""
    numbers = [int(identifier[1:]) for identifier in identifiers]
    sorted_numbers = sorted(numbers)
    if numbers != sorted_numbers:
        return [
            Finding(
                code="PLAN022",
                severity=Severity.WARNING,
                message=(
                    f"{kind} canonical identifiers are not strictly "
                    "monotonic in document order; an earlier row carries "
                    "a higher number than a later one."
                ),
                line_number=0,
                fix_hint=(
                    "Document order may diverge from canonical-id order "
                    "by design (insert-between scenarios). Verify this "
                    "ordering reflects writer intent rather than a "
                    "hand-edit error."
                ),
                autofixable=False,
            ),
        ]
    return []
