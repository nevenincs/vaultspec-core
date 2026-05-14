"""Display-path correctness detection rule (``PLAN030``).

Compares each row's stored display path against the value computed
from its current ancestor chain. Drift typically means a Step or
Phase was hand-moved without re-rendering; ``vaultspec-core vault plan check --fix``
recomputes the paths idempotently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.plan.display_path import compute_display_paths

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_display_path"]


def check_display_path(plan: Plan) -> list[Finding]:
    """Detect rows whose stored display path differs from the computed value."""
    table = compute_display_paths(plan)
    findings: list[Finding] = []

    for step in plan.steps:
        expected = table.steps.get(step.canonical_id)
        if expected is not None and expected != step.display_path:
            findings.append(
                Finding(
                    code="PLAN030",
                    severity=Severity.WARNING,
                    message=(
                        f"Step {step.canonical_id} display path "
                        f"'{step.display_path}' diverges from the value "
                        f"computed from its current ancestor chain "
                        f"('{expected}')."
                    ),
                    line_number=step.line_number,
                    fix_hint=(
                        "Run 'vaultspec-core vault plan check --fix' to "
                        "recompute the display path against the current "
                        "grouping."
                    ),
                    autofixable=True,
                ),
            )

    for phase in plan.phases:
        expected = table.phases.get(phase.canonical_id)
        if expected is not None and expected != phase.display_path:
            findings.append(
                Finding(
                    code="PLAN030",
                    severity=Severity.WARNING,
                    message=(
                        f"Phase {phase.canonical_id} heading display path "
                        f"'{phase.display_path}' diverges from the value "
                        f"computed from its current Wave parent "
                        f"('{expected}')."
                    ),
                    line_number=phase.line_number,
                    fix_hint=(
                        "Run 'vaultspec-core vault plan check --fix' to "
                        "recompute the Phase heading path."
                    ),
                    autofixable=True,
                ),
            )

    return findings
