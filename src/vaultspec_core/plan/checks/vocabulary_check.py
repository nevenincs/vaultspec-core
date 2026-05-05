"""Approved-structural-vocabulary detection rule.

Implementation arrives in W02.P02.S50.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.checks._base import Finding
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_vocabulary"]


def check_vocabulary(plan: Plan, source_text: str) -> list[Finding]:  # noqa: ARG001
    """Stub; concrete checks land in W02.P02.S50."""
    return []
