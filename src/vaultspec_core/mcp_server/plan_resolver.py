"""Shared feature-or-stem plan resolver for the plan-domain MCP tools.

The ``plan_progress`` and ``plan_edit`` tools address a plan by either its
filename stem (or path) or its feature tag.  Both route the address through
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

    def __init__(self, target: str, candidates: list[str]) -> None:
        self.target = target
        self.candidates = candidates
        if not candidates:
            detail = "no plan document matches it by stem, path, or feature tag"
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

    Resolution precedence mirrors the orientation trace resolver: an exact
    plan stem (or a path whose stem matches a plan) wins first, then a
    feature tag matching exactly one plan.  A feature tag matching several
    plans is ambiguous and raises rather than picking one.

    Args:
        root_dir: The project root whose ``.vault/`` is searched.
        target: A plan stem, a plan path (absolute or relative, with or
            without ``.md``), or a feature tag (with or without a leading
            ``#``).

    Returns:
        The uniquely :class:`ResolvedPlan`.

    Raises:
        PlanResolutionError: When the address matches no plan, or matches a
            feature that owns more than one plan.
    """
    from vaultspec_core.vaultcore.query import list_documents

    cleaned = target.strip()
    plans = list_documents(root_dir, doc_type="plan")

    stem_wanted = Path(cleaned).stem if cleaned else cleaned
    for doc in plans:
        if doc.name in (cleaned, stem_wanted):
            return _to_resolved(doc)

    feature = cleaned.lstrip("#")
    feature_matches = [doc for doc in plans if doc.feature == feature]
    if len(feature_matches) == 1:
        return _to_resolved(feature_matches[0])
    if len(feature_matches) > 1:
        raise PlanResolutionError(target, sorted(doc.name for doc in feature_matches))

    raise PlanResolutionError(target, [])


def _to_resolved(doc: VaultDocument) -> ResolvedPlan:
    """Adapt a :class:`VaultDocument` into a :class:`ResolvedPlan`."""
    return ResolvedPlan(path=doc.path, stem=doc.name, feature=doc.feature)
