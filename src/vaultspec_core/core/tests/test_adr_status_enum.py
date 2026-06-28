"""Tests for the canonical :class:`AdrStatus` taxonomy."""

import pytest

from ..enums import AdrStatus

pytestmark = [pytest.mark.unit]


class TestAdrStatusMembers:
    def test_canonical_set_is_exactly_five_values(self):
        """The taxonomy is the contract; guard it against silent drift."""
        assert {s.value for s in AdrStatus} == {
            "proposed",
            "accepted",
            "rejected",
            "superseded",
            "deprecated",
        }

    def test_supersede_writer_value_matches_member(self):
        """The supersede writer commits to this exact spelling."""
        assert AdrStatus.SUPERSEDED.value == "superseded"


class TestAdrStatusFromToken:
    @pytest.mark.parametrize(
        "token,expected",
        [
            ("proposed", AdrStatus.PROPOSED),
            ("accepted", AdrStatus.ACCEPTED),
            ("rejected", AdrStatus.REJECTED),
            ("superseded", AdrStatus.SUPERSEDED),
            ("deprecated", AdrStatus.DEPRECATED),
        ],
    )
    def test_resolves_canonical_tokens(self, token, expected):
        assert AdrStatus.from_token(token) is expected

    @pytest.mark.parametrize(
        "token",
        ["Accepted", "  accepted  ", "`accepted`", " `Accepted` "],
    )
    def test_resolves_leniently(self, token):
        """Case, whitespace, and backtick quoting are tolerated."""
        assert AdrStatus.from_token(token) is AdrStatus.ACCEPTED

    @pytest.mark.parametrize("token", ["", "approved", "done", "wip", "  "])
    def test_off_taxonomy_returns_none(self, token):
        assert AdrStatus.from_token(token) is None

    def test_none_returns_none(self):
        assert AdrStatus.from_token(None) is None
