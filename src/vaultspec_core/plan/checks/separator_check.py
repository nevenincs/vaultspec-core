"""Separator-convention detection rule.

Implementation arrives in W02.P02.S51.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.checks._base import Finding

__all__ = ["check_separator"]


def check_separator(source_text: str) -> list[Finding]:  # noqa: ARG001
    """Stub; concrete checks land in W02.P02.S51."""
    return []
