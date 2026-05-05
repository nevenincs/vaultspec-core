"""Plan-document query implementation backing ``vault plan query``.

Per the CLI ADR's *query* section, the query language has two layers:

- **Selectors** scope the query to a container subtree. At most one
  selector applies per invocation; ``--phase P##`` is more specific
  than ``--wave W##`` and wins when both are supplied.
- **Predicates** filter Step rows within the selected scope.
  Predicates compose with ``AND`` semantics.

The selectors and predicates are pure functions of a parsed
:class:`Plan`. The CLI command in W02.P07 wires them to argparse /
typer flags and emits the resulting Steps either as human or JSON
output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import Plan, Step

__all__ = ["QueryFilter", "QueryResult", "query_steps"]


@dataclass
class QueryFilter:
    """Filter parameters for :func:`query_steps`.

    Attributes:
        scope_wave: When set, restrict results to Steps under this Wave.
        scope_phase: When set, restrict results to Steps under this
            Phase. Wins over ``scope_wave`` when both are supplied.
        only_open: When ``True``, include only Steps with ``[ ]``.
        only_closed: When ``True``, include only Steps with ``[x]``.
        tier_match: When set, return an empty result unless the plan's
            declared tier equals this value.
    """

    scope_wave: str | None = None
    scope_phase: str | None = None
    only_open: bool = False
    only_closed: bool = False
    tier_match: Tier | None = None


@dataclass
class QueryResult:
    """Outcome of :func:`query_steps`.

    Attributes:
        plan_tier: The plan's declared tier.
        matched: Step rows in document order that satisfied every
            selector and predicate.
        total: Number of Step rows in the plan before filtering;
            useful for emitting a ``matched / total`` summary line.
    """

    plan_tier: Tier
    matched: list[Step]
    total: int


def query_steps(plan: Plan, query_filter: QueryFilter) -> QueryResult:
    """Apply ``query_filter`` to ``plan`` and return matching Steps.

    Args:
        plan: Parsed :class:`Plan` model.
        query_filter: Selectors and predicates to apply.

    Returns:
        :class:`QueryResult` with matched Steps in document order.
    """
    if (
        query_filter.tier_match is not None
        and query_filter.tier_match is not plan.frontmatter.tier
    ):
        return QueryResult(
            plan_tier=plan.frontmatter.tier,
            matched=[],
            total=len(plan.steps),
        )

    candidate_steps = _scope_steps(plan, query_filter)
    matched = [step for step in candidate_steps if _accepts(step, query_filter)]
    return QueryResult(
        plan_tier=plan.frontmatter.tier,
        matched=matched,
        total=len(plan.steps),
    )


def _scope_steps(plan: Plan, query_filter: QueryFilter) -> list[Step]:
    """Resolve the selector chain to a candidate list of Steps."""
    if query_filter.scope_phase is not None:
        for phase in plan.phases:
            if phase.canonical_id == query_filter.scope_phase:
                return list(phase.steps)
        return []
    if query_filter.scope_wave is not None:
        for wave in plan.waves:
            if wave.canonical_id == query_filter.scope_wave:
                return [step for phase in wave.phases for step in phase.steps]
        return []
    return list(plan.steps)


def _accepts(step: Step, query_filter: QueryFilter) -> bool:
    """Apply the open/closed predicate to a candidate Step."""
    if query_filter.only_open and step.checked:
        return False
    return not (query_filter.only_closed and not step.checked)
