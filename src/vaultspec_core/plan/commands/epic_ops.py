"""Epic intent show / edit commands (W02.P04.S75).

The Epic frame is implicit at L4; there is no Epic add / remove /
move (those operations are achieved via ``tier promote --to L4`` and
``tier demote`` from L4). The only Epic-level mutating verb is
editing the intent block prose, which holds the project-management
association declaration mandated by the convention ADR.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.parser import EpicIntent

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["EpicIntentError", "edit_epic_intent", "show_epic_intent"]


class EpicIntentError(ValueError):
    """Raised when an Epic intent operation runs against a non-L4 plan."""


def show_epic_intent(plan: Plan) -> str:
    """Return the Epic intent paragraph text.

    Raises:
        EpicIntentError: When the plan tier is not L4 or the Epic
            intent block is missing on an L4 plan.
    """
    if plan.frontmatter.tier is not Tier.L4:
        msg = (
            f"Epic intent is only defined at L4; this plan is "
            f"{plan.frontmatter.tier.value}."
        )
        raise EpicIntentError(msg)
    if plan.epic_intent is None:
        msg = "L4 plan is missing its required '## Epic intent' block"
        raise EpicIntentError(msg)
    return plan.epic_intent.text


def edit_epic_intent(plan: Plan, *, text: str) -> EpicIntent:
    """Replace the Epic intent paragraph text with ``text``.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        text: New Epic intent paragraph; must contain the external
            project-management association declaration per the
            convention ADR.

    Raises:
        EpicIntentError: When the plan tier is not L4.
    """
    if plan.frontmatter.tier is not Tier.L4:
        msg = (
            f"Epic intent edits require an L4 plan; this plan is "
            f"{plan.frontmatter.tier.value}."
        )
        raise EpicIntentError(msg)
    if plan.epic_intent is None:
        plan.epic_intent = EpicIntent(text=text, line_number=0)
    else:
        plan.epic_intent.text = text
    return plan.epic_intent
