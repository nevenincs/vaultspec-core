"""Finding objects and the cross-rule collection harness.

A :class:`Finding` is the canonical diagnostic unit emitted by every
detection rule. The :func:`collect_all` harness composes the seven
detection rules from the convention ADR's *check* surface into one
report; ``vaultspec-core vault plan check`` exits non-zero when any
:class:`Severity.ERROR` finding is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["Finding", "Severity", "collect_all", "has_errors"]


class Severity(StrEnum):
    """Severity ladder for ``vaultspec-core vault plan check`` findings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    """One diagnostic emitted by a detection rule.

    Attributes:
        code: Stable rule identifier (``PLAN###``). External tools may
            bind to these codes to filter or suppress findings.
        severity: One of :class:`Severity`.
        message: Human-readable description of the violation.
        line_number: 1-based source line where the violation was
            observed; ``0`` when the finding is document-wide.
        fix_hint: Short suggestion for resolving the violation, shown
            alongside the message in human output.
        autofixable: ``True`` when ``vaultspec-core vault plan check --fix`` can
            resolve the finding without writer intervention.
    """

    code: str
    severity: Severity
    message: str
    line_number: int = 0
    fix_hint: str = ""
    autofixable: bool = False


def collect_all(plan: Plan, source_text: str) -> list[Finding]:
    """Run every detection rule and concatenate the findings.

    Args:
        plan: Parsed :class:`Plan` model.
        source_text: Original markdown text; needed by detection rules
            that scan raw lines (separator convention, structural-noun
            occurrences in headings).

    Returns:
        Flat list of :class:`Finding` instances in the order each rule
        produced them. Rules run in the canonical order: frontmatter,
        hierarchy, identifiers, display path, row contract, vocabulary,
        separator.
    """
    from vaultspec_core.plan.checks.display_path_check import check_display_path
    from vaultspec_core.plan.checks.frontmatter_check import check_frontmatter
    from vaultspec_core.plan.checks.hierarchy_check import check_hierarchy
    from vaultspec_core.plan.checks.identifiers_check import check_identifiers
    from vaultspec_core.plan.checks.row_contract_check import check_row_contract
    from vaultspec_core.plan.checks.separator_check import check_separator
    from vaultspec_core.plan.checks.vocabulary_check import check_vocabulary

    findings: list[Finding] = []
    findings.extend(check_frontmatter(plan))
    findings.extend(check_hierarchy(plan))
    findings.extend(check_identifiers(plan, source_text))
    findings.extend(check_display_path(plan))
    findings.extend(check_row_contract(plan, source_text))
    findings.extend(check_vocabulary(plan, source_text))
    findings.extend(check_separator(source_text))
    return findings


def has_errors(findings: list[Finding]) -> bool:
    """Return ``True`` when at least one finding is an :class:`Severity.ERROR`."""
    return any(finding.severity is Severity.ERROR for finding in findings)
