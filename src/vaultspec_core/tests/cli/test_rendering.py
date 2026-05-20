"""Tests for the canonical outcome vocabulary in :mod:`cli.rendering`.

Covers the seven-word taxonomy, the aggregate rule, and the guarantee
that the text and JSON surfaces consume one :class:`OutcomeItem` list and
therefore cannot drift apart.
"""

from __future__ import annotations

import dataclasses
from typing import cast

import pytest

from vaultspec_core.cli.rendering import (
    OUTCOME_STYLE,
    Outcome,
    OutcomeItem,
    aggregate_outcome,
    count_outcomes,
    outcomes_as_json,
    render_outcomes,
)
from vaultspec_core.console import reset_console


@pytest.mark.unit
class TestOutcomeEnum:
    def test_seven_word_taxonomy_plus_mixed(self):
        assert {o.value for o in Outcome} == {
            "created",
            "updated",
            "unchanged",
            "removed",
            "restored",
            "skipped",
            "failed",
            "mixed",
        }

    def test_every_outcome_has_a_style(self):
        for outcome in Outcome:
            glyph, colour = OUTCOME_STYLE[outcome]
            assert glyph
            assert colour

    def test_str_of_member_is_the_lowercase_word(self):
        assert str(Outcome.CREATED) == "created"


@pytest.mark.unit
class TestOutcomeItem:
    def test_item_is_frozen(self):
        item = OutcomeItem(name="rule-a", outcome=Outcome.CREATED)
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.name = "rule-b"  # ty: ignore[invalid-assignment]

    def test_detail_defaults_to_empty(self):
        assert OutcomeItem(name="x", outcome=Outcome.SKIPPED).detail == ""


@pytest.mark.unit
class TestAggregateOutcome:
    def test_empty_set_aggregates_to_unchanged(self):
        assert aggregate_outcome([]) == Outcome.UNCHANGED

    def test_unanimous_outcome_is_returned(self):
        items = [
            OutcomeItem(name="a", outcome=Outcome.CREATED),
            OutcomeItem(name="b", outcome=Outcome.CREATED),
        ]
        assert aggregate_outcome(items) == Outcome.CREATED

    def test_divergent_outcomes_aggregate_to_mixed(self):
        items = [
            OutcomeItem(name="a", outcome=Outcome.CREATED),
            OutcomeItem(name="b", outcome=Outcome.UPDATED),
        ]
        assert aggregate_outcome(items) == Outcome.MIXED


@pytest.mark.unit
class TestCountOutcomes:
    def test_counts_per_outcome(self):
        items = [
            OutcomeItem(name="a", outcome=Outcome.CREATED),
            OutcomeItem(name="b", outcome=Outcome.CREATED),
            OutcomeItem(name="c", outcome=Outcome.SKIPPED),
        ]
        counts = count_outcomes(items)
        assert counts == {Outcome.CREATED: 2, Outcome.SKIPPED: 1}


@pytest.mark.unit
class TestOutcomesAsJson:
    def test_status_is_the_aggregate_word(self):
        items = [OutcomeItem(name="a", outcome=Outcome.UPDATED)]
        payload = outcomes_as_json(items)
        assert payload["status"] == "updated"

    def test_empty_invocation_reports_unchanged(self):
        assert outcomes_as_json([])["status"] == "unchanged"

    def test_item_records_carry_name_and_outcome(self):
        items = [OutcomeItem(name="rule-a", outcome=Outcome.CREATED)]
        records = cast("list[dict[str, str]]", outcomes_as_json(items)["items"])
        assert records[0] == {"name": "rule-a", "outcome": "created"}

    def test_detail_is_omitted_when_blank_and_present_otherwise(self):
        items = [
            OutcomeItem(name="a", outcome=Outcome.SKIPPED, detail="excluded by policy"),
            OutcomeItem(name="b", outcome=Outcome.CREATED),
        ]
        records = cast("list[dict[str, str]]", outcomes_as_json(items)["items"])
        assert records[0]["detail"] == "excluded by policy"
        assert "detail" not in records[1]


@pytest.mark.unit
class TestRenderOutcomes:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_text_surface_shares_one_taxonomy_with_json(self, capsys):
        items = [
            OutcomeItem(name="rule-a", outcome=Outcome.CREATED),
            OutcomeItem(name="rule-b", outcome=Outcome.SKIPPED, detail="exists"),
        ]
        render_outcomes(items, title="Sync")
        out = capsys.readouterr().out
        assert "Sync" in out
        assert "rule-a" in out
        assert "rule-b" in out
        # The per-outcome summary uses the same canonical words as JSON.
        assert "1 created" in out
        assert "1 skipped" in out
        assert "exists" in out

    def test_empty_invocation_renders_without_error(self, capsys):
        render_outcomes([])
        assert "Result" in capsys.readouterr().out
