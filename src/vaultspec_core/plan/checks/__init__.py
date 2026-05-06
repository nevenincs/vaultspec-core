"""Detection rules for ``vault plan check``.

Every detection rule is a pure function that takes a parsed
:class:`vaultspec_core.plan.parser.Plan` (and the original markdown
text where line-level diagnostics are required) and returns a list of
:class:`Finding` objects. The harness in this package collects results
from all rules, filters by severity, and surfaces a unified report.
"""

from __future__ import annotations

from vaultspec_core.plan.checks._base import (
    Finding,
    Severity,
    collect_all,
    has_errors,
)

__all__ = ["Finding", "Severity", "collect_all", "has_errors"]
