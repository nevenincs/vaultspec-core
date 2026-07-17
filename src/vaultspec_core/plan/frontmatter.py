"""Plan-frontmatter parsing and validation.

Implements the plan-frontmatter contract from the plan-hardening
convention:

- ``tier``: mandatory unquoted scalar, one of ``L1``, ``L2``, ``L3``, ``L4``.
  Pre-existing plans without the field default to ``L2``; the field is
  reported as a warning with a migration hint.
- ``related``: YAML list of quoted wiki-links pointing to authorising
  documents; required when the plan contains at least one Step row.
- ``tags``: YAML list with at least the directory tag (``#plan``) and one
  feature tag (``#<feature>``).
- ``date``: ``yyyy-mm-dd`` ISO date.

Defers low-level YAML parsing to :mod:`vaultspec_core.vaultcore.parser`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from vaultspec_core.vaultcore.parser import parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "PlanFrontmatter",
    "PlanFrontmatterError",
    "Tier",
    "parse_plan_frontmatter",
]


class Tier(StrEnum):
    """Complexity tier declared in a plan document's frontmatter.

    The tier determines which structural containers a plan emits per the
    convention ADR's *Hierarchy and tiers* section.
    """

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class PlanFrontmatterError(ValueError):
    """Raised when a plan document's frontmatter violates the contract."""


@dataclass
class PlanFrontmatter:
    """Validated plan-document frontmatter.

    Attributes:
        tier: Complexity tier (``L1``-``L4``).
        related: Wiki-link references to authorising documents (ADR,
            research, reference, prior plan).
        tags: Tag list; first entry is the directory tag (``#plan``),
            subsequent entries include the feature tag.
        date: ISO ``yyyy-mm-dd`` date string from the frontmatter.
        legacy_tier_default: ``True`` when ``tier`` was missing in the
            source document and defaulted to ``L2``; the writer agent or
            ``vaultspec-core vault plan check --fix`` should add the field on
            first edit.
    """

    tier: Tier
    related: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    date: str = ""
    legacy_tier_default: bool = False


def parse_plan_frontmatter(source: str | Path) -> PlanFrontmatter:
    """Parse and validate a plan document's frontmatter.

    Args:
        source: Either the full markdown text of a plan document or a path
            to one. When a path is given, the file is read with UTF-8
            encoding.

    Returns:
        Validated :class:`PlanFrontmatter`.

    Raises:
        PlanFrontmatterError: When ``tier`` is present with an invalid value,
            ``tags`` is missing the directory or feature tag, ``related`` is
            present but malformed, or the YAML frontmatter is itself
            unparseable.
    """
    text = _coerce_to_text(source)
    raw, _body = parse_frontmatter(text)

    tier_value, legacy_default = _coerce_tier(raw.get("tier"))
    related = _coerce_string_list(raw.get("related"), field_name="related")
    tags = _coerce_string_list(raw.get("tags"), field_name="tags")
    date = _coerce_date(raw.get("date"))

    _require_tag(tags, "#plan")
    _require_feature_tag(tags)

    return PlanFrontmatter(
        tier=tier_value,
        related=related,
        tags=tags,
        date=date,
        legacy_tier_default=legacy_default,
    )


def _coerce_to_text(source: str | Path) -> str:
    """Return raw markdown text from a string or path."""
    from pathlib import Path as _Path

    if isinstance(source, _Path):
        return source.read_text(encoding="utf-8")
    return source


def _coerce_tier(value: object) -> tuple[Tier, bool]:
    """Validate ``tier`` and apply the legacy ``L2`` default when missing.

    Returns:
        Tuple of (resolved :class:`Tier`, ``True`` when the value was
        missing and the legacy ``L2`` default was applied).
    """
    if value is None:
        return Tier.L2, True
    if not isinstance(value, str):
        raise PlanFrontmatterError(
            f"tier must be an unquoted scalar (L1..L4), got {type(value).__name__}",
        )
    try:
        return Tier(value), False
    except ValueError as exc:
        raise PlanFrontmatterError(
            f"tier must be one of L1, L2, L3, L4; got {value!r}",
        ) from exc


def _coerce_string_list(value: object, *, field_name: str) -> list[str]:
    """Ensure ``value`` is a list of strings, returning an empty list when absent."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlanFrontmatterError(
            f"{field_name} must be a YAML list, got {type(value).__name__}",
        )
    coerced: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise PlanFrontmatterError(
                f"{field_name} entries must be strings, got {type(entry).__name__}",
            )
        coerced.append(entry)
    return coerced


def _coerce_date(value: object) -> str:
    """Validate the date scalar; return an empty string when absent."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PlanFrontmatterError(
            f"date must be a string, got {type(value).__name__}",
        )
    return value


def _require_tag(tags: list[str], required: str) -> None:
    """Raise :class:`PlanFrontmatterError` when ``required`` is absent from ``tags``."""
    if required not in tags:
        raise PlanFrontmatterError(
            f"tags must include the directory tag {required!r}",
        )


def _require_feature_tag(tags: list[str]) -> None:
    """Raise :class:`PlanFrontmatterError` when no ``#<feature>`` tag exists."""
    for tag in tags:
        if tag.startswith("#") and tag != "#plan" and not _is_directory_tag(tag):
            return
    raise PlanFrontmatterError(
        "tags must include a feature tag (e.g., '#editor-demo')",
    )


_DIRECTORY_TAGS = frozenset(
    {"#adr", "#audit", "#exec", "#index", "#plan", "#reference", "#research"},
)


def _is_directory_tag(tag: str) -> bool:
    """Return ``True`` if ``tag`` is one of the canonical directory tags."""
    return tag in _DIRECTORY_TAGS
