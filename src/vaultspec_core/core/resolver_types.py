"""Shared result types for the resolution engine.

Holds :class:`ResolutionStep` and :class:`ResolutionPlan`, the accumulator types
every ``resolver_*`` rule module writes into. Split out from ``resolver.py`` so
the per-domain rule modules can depend on the types without importing the
orchestrator itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diagnosis.signals import ResolutionAction


@dataclass
class ResolutionStep:
    """A single corrective action within a :class:`ResolutionPlan`.

    Args:
        action: The :class:`~vaultspec_core.core.diagnosis.signals.ResolutionAction`
            to perform.
        target: What the action operates on (provider name, file path, etc.).
        reason: Human-readable explanation of why this step is needed.
    """

    action: ResolutionAction
    target: str
    reason: str


@dataclass
class ResolutionPlan:
    """Accumulated plan of resolution steps, warnings, and conflicts.

    Args:
        steps: Ordered list of :class:`ResolutionStep` to execute.
        warnings: Non-blocking advisories emitted before execution.
        conflicts: Blocking issues that prevent execution.
    """

    steps: list[ResolutionStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """Return ``True`` if the plan has unresolved conflicts."""
        return len(self.conflicts) > 0
