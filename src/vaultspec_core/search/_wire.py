"""The one projection of a ranked hit that every search surface carries.

The MCP ``search`` tool and ``vault search --json`` answer the same question
with the same hits, so they carry each hit under the same keys and at the same
precision. Both build their payload from :func:`hit_fields` rather than each
choosing its own names and rounding.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ._models import Excerpt, SearchHit

__all__ = ["SCORE_PLACES", "hit_fields"]

#: Decimal places kept of each probability. Three separate any two hits a
#: caller could act on; the rest is digits the model reads and cannot use.
SCORE_PLACES: Final = 3


def _excerpt_fields(excerpt: Excerpt | None) -> dict[str, object] | None:
    """Return *excerpt*'s fields as they are, or ``None`` when there is none."""
    return None if excerpt is None else dataclasses.asdict(excerpt)


def hit_fields(hit: SearchHit) -> dict[str, object]:
    """Project one ranked hit onto the fields a reply carries.

    ``name`` is left out because it is the stem of ``path``. The record type
    travels as ``type``, and each probability is rounded to
    :data:`SCORE_PLACES`. An excerpt the search did not choose is absent
    rather than ``None``. Excerpts are carried exactly as the search package
    bounded them.

    Args:
        hit: The ranked record.

    Returns:
        The hit's JSON-ready fields.
    """
    fields: dict[str, object] = {
        "path": hit.path,
        "type": hit.doc_type.value,
        "feature": hit.feature,
        "date": hit.date,
        "title": hit.title,
        "score": round(hit.score, SCORE_PLACES),
        "answers": round(hit.answers, SCORE_PLACES),
        "premise_conflict": round(hit.premise_conflict, SCORE_PLACES),
        "blob_hash": hit.blob_hash,
    }
    for key, excerpt in (("excerpt", hit.excerpt), ("supporting", hit.supporting)):
        projected = _excerpt_fields(excerpt)
        if projected is not None:
            fields[key] = projected
    return fields
