"""Marker base class shared by every command-handler typed exception.

Every typed exception raised by a ``vault plan`` command handler
(``StepNotFoundError``, ``MoveStepError``, ``AddPhaseError``,
``PhaseRenumberError``, ``EpicIntentError``, ``Promote / DemoteError``,
``Move{Step,Phase,Wave}Error``, etc.) inherits from
:class:`PlanCommandError` in addition to its semantic parent
(``KeyError`` for missing-id lookups, ``ValueError`` for everything else).

The marker exists so the CLI's ``_render_user_errors`` decorator can
catch the union of typed handler exceptions with a single symbol
rather than enumerating each class explicitly. Adding a new typed
error therefore requires only that the new class inherits from
:class:`PlanCommandError` somewhere in its MRO; no further wiring
in the CLI layer is needed.
"""

from __future__ import annotations

__all__ = ["PlanCommandError"]


class PlanCommandError(Exception):
    """Marker base for every command-handler typed exception."""
