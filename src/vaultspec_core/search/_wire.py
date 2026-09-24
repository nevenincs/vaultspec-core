"""The one projection of a search outcome that every search surface carries.

The MCP ``search`` tool and ``vault search --json`` answer the same question
with the same result, so they carry it under the same keys, at the same
precision and with the same next step. Both build their payload from
:func:`outcome_fields` rather than each choosing its own names, rounding and
which keys apply.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

from ._remediation import remediation

if TYPE_CHECKING:
    from ._models import Excerpt, NextStep, SearchHit, SearchOutcome

__all__ = ["SCORE_PLACES", "hit_fields", "outcome_fields"]

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


def _next_step_fields(step: NextStep) -> dict[str, object]:
    """Project a next step onto plain values."""
    return {
        "kind": step.kind.value,
        "types": [doc_type.value for doc_type in step.types],
        "command": step.command,
    }


def outcome_fields(outcome: SearchOutcome) -> dict[str, object]:
    """Project a search outcome onto the fields a reply carries.

    ``status``, ``answered`` and ``hits`` are always present. A ranked page
    adds its ``verdict`` and window fields; an outcome that did not rank adds
    its ``reason`` when it failed, its ``next_step`` and the ``remediation``
    sentence that words both. ``usage`` is present whenever a request was
    sent. Keys that do not apply are absent rather than ``None``, and the
    query is not echoed: the caller supplied it.

    Args:
        outcome: The outcome of one search.

    Returns:
        The outcome's JSON-ready fields.
    """
    fields: dict[str, object] = {
        "status": outcome.status.value,
        "answered": outcome.answered,
    }
    if outcome.verdict is not None:
        fields["verdict"] = outcome.verdict.value
    fields["hits"] = [hit_fields(hit) for hit in outcome.hits]
    if outcome.window is not None:
        fields.update(outcome.window.as_fields())
    if outcome.reason is not None:
        fields["reason"] = outcome.reason.value
    if outcome.next_step is not None:
        fields["next_step"] = _next_step_fields(outcome.next_step)
        fields["remediation"] = remediation(outcome)
    if outcome.usage is not None:
        fields["usage"] = dataclasses.asdict(outcome.usage)
    return fields
