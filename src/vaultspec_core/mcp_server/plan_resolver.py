"""Shared feature-or-stem plan resolver for the plan-domain MCP tools.

The ``plan_progress`` and ``plan_edit`` tools address a plan by either its
filename stem or its feature tag. Both route the address through
:func:`resolve_plan`, which reuses
:func:`~vaultspec_core.vaultcore.query.list_documents` so the resolver and the
rest of the surface agree on what a plan is.  A feature that maps to more than
one plan is a structured :class:`PlanResolutionError`, never a silent guess -
the ADR's "unresolvable target" whole-call failure, surfaced to the caller so
it can disambiguate by stem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.vaultcore.query import VaultDocument

__all__ = ["PlanResolutionError", "ResolvedPlan", "resolve_plan"]


class PlanResolutionError(ValueError):
    """Raised when a plan address resolves to zero or many plan documents.

    Carries the candidate stems so a caller (or the host) can disambiguate
    by re-addressing with a unique stem rather than a feature tag.

    Attributes:
        target: The raw address string that could not be uniquely resolved.
        candidates: The stems that matched the address, empty when nothing
            matched.
    """

    def __init__(
        self, target: str, candidates: list[str], *, reason: str | None = None
    ) -> None:
        self.target = target
        self.candidates = candidates
        if reason is not None:
            detail = reason
        elif not candidates:
            detail = "no plan document matches it by stem or feature tag"
        else:
            joined = ", ".join(candidates)
            detail = (
                f"{len(candidates)} plans match the feature; address one by "
                f"stem instead: {joined}"
            )
        super().__init__(f"Cannot resolve plan {target!r}: {detail}.")


@dataclass
class ResolvedPlan:
    """A plan address resolved to a single backing document.

    Attributes:
        path: Absolute filesystem path to the plan document.
        stem: The plan's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
    """

    path: Path
    stem: str
    feature: str | None


def resolve_plan(root_dir: Path, target: str) -> ResolvedPlan:
    """Resolve a plan address to a unique plan document.

    An exact plan stem wins first, then a feature tag matching exactly one
    plan. A feature tag matching several plans is ambiguous and raises
    rather than picking one.

    Args:
        root_dir: The project root whose ``.vault/`` is searched.
        target: A plan stem (with or without ``.md``), or a feature tag
            (with or without a leading ``#``).

    Returns:
        The uniquely :class:`ResolvedPlan`.

    Raises:
        PlanResolutionError: When the address matches no plan, or matches a
            feature that owns more than one plan.
    """
    from vaultspec_core.plan.targets import (
        validate_plan_identifier,
        workspace_plan_directory,
        workspace_plan_file,
    )
    from vaultspec_core.vaultcore.query import list_documents

    cleaned = target.strip()
    try:
        validate_plan_identifier(cleaned)
        workspace_plan_directory(root_dir)
    except ValueError as exc:
        raise PlanResolutionError(target, [], reason=str(exc)) from exc
    plans = list_documents(root_dir, doc_type="plan")

    def resolved_plan(doc: VaultDocument) -> ResolvedPlan:
        try:
            path = workspace_plan_file(root_dir, doc.path)
        except ValueError as exc:
            raise PlanResolutionError(target, [], reason=str(exc)) from exc
        return ResolvedPlan(path=path, stem=doc.name, feature=doc.feature)

    stem_wanted = Path(cleaned).stem if cleaned else cleaned
    for doc in plans:
        if doc.name in (cleaned, stem_wanted):
            return resolved_plan(doc)

    feature = cleaned.lstrip("#")
    feature_matches = [doc for doc in plans if doc.feature == feature]
    if len(feature_matches) == 1:
        return resolved_plan(feature_matches[0])
    if len(feature_matches) > 1:
        raise PlanResolutionError(target, sorted(doc.name for doc in feature_matches))

    raise PlanResolutionError(target, [])
