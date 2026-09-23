"""The next-step sentence every search surface reports."""

from __future__ import annotations

import pytest

from vaultspec_core.core.discovery_guidance import SEARCH_ADR
from vaultspec_core.search import (
    SearchOutcome,
    SearchStatus,
    UnavailableReason,
    remediation,
)
from vaultspec_core.search._credential import CREDENTIAL_VARIABLE

pytestmark = [pytest.mark.unit]


def test_a_ranked_outcome_needs_no_remediation() -> None:
    assert remediation(SearchOutcome(status=SearchStatus.OK, query="q")) is None


def test_not_configured_names_the_variable_and_the_rag_fallback() -> None:
    text = remediation(SearchOutcome(status=SearchStatus.NOT_CONFIGURED, query="q"))

    assert text is not None
    assert CREDENTIAL_VARIABLE in text
    assert SEARCH_ADR in text


@pytest.mark.parametrize("reason", list(UnavailableReason))
def test_every_unavailable_reason_has_its_own_next_step(
    reason: UnavailableReason,
) -> None:
    text = remediation(
        SearchOutcome(status=SearchStatus.UNAVAILABLE, query="q", reason=reason)
    )

    assert text is not None
    assert SEARCH_ADR in text


def test_unavailable_sentences_are_distinct() -> None:
    texts = {
        remediation(SearchOutcome(status=SearchStatus.UNAVAILABLE, query="q", reason=r))
        for r in UnavailableReason
    }

    assert len(texts) == len(UnavailableReason)
