"""The outcome wording both search surfaces print."""

from __future__ import annotations

import pytest

from vaultspec_core.search import (
    PREMISE_CONFLICT_THRESHOLD,
    SearchHit,
    SearchStatus,
    SearchVerdict,
    UnavailableReason,
    outcome_label,
    premise_note,
    unscored_note,
)
from vaultspec_core.vaultcore.models import DocType

pytestmark = [pytest.mark.unit]


def _hit(premise_conflict: float) -> SearchHit:
    return SearchHit(
        name="n",
        path=".vault/adr/n.md",
        doc_type=DocType.ADR,
        feature="f",
        date="2026-01-02",
        title="t",
        score=0.5,
        answers=0.5,
        premise_conflict=premise_conflict,
        excerpt=None,
        supporting=None,
        blob_hash="0" * 40,
    )


class TestOutcomeLabel:
    @pytest.mark.parametrize("verdict", list(SearchVerdict))
    def test_a_ranked_page_is_labelled_by_its_verdict(
        self, verdict: SearchVerdict
    ) -> None:
        assert outcome_label(SearchStatus.OK, verdict, None) == verdict.sentence

    def test_a_decline_is_labelled_by_its_outcome(self) -> None:
        label = outcome_label(SearchStatus.NOT_CONFIGURED, None, None)

        assert label == "not configured"

    @pytest.mark.parametrize("reason", list(UnavailableReason))
    def test_a_failure_names_its_reason(self, reason: UnavailableReason) -> None:
        label = outcome_label(SearchStatus.UNAVAILABLE, None, reason)

        assert label == f"unavailable ({reason.value})"


class TestNotes:
    def test_nothing_unscored_needs_no_note(self) -> None:
        assert unscored_note(0) is None

    @pytest.mark.parametrize(("count", "noun"), [(1, "record"), (3, "records")])
    def test_the_unscored_note_counts_the_records(self, count: int, noun: str) -> None:
        note = unscored_note(count)

        assert note is not None
        assert note.startswith(f"{count} {noun} ")

    def test_a_hit_below_the_threshold_has_no_premise_note(self) -> None:
        assert premise_note(_hit(PREMISE_CONFLICT_THRESHOLD - 0.01)) is None

    def test_the_premise_note_carries_the_probability(self) -> None:
        note = premise_note(_hit(0.875))

        assert note is not None
        assert note.endswith("(0.88)")
