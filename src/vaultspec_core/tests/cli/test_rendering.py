"""Tests for the canonical outcome vocabulary in :mod:`cli.rendering`.

Covers the seven-word taxonomy, the aggregate rule, and the guarantee
that the text and JSON surfaces consume one :class:`OutcomeItem` list and
therefore cannot drift apart.
"""

from __future__ import annotations

import dataclasses
import json
from typing import cast

import pytest

from vaultspec_core.cli.rendering import (
    OUTCOME_STYLE,
    Outcome,
    OutcomeItem,
    aggregate_outcome,
    count_outcomes,
    emit_outcomes,
    outcomes_as_json,
    render_outcomes,
    sync_outcomes,
)
from vaultspec_core.console import reset_console
from vaultspec_core.core.types import SyncResult


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

    def test_group_is_recorded_when_present_and_omitted_when_blank(self):
        items = [
            OutcomeItem(name="a", outcome=Outcome.CREATED, group="claude"),
            OutcomeItem(name="b", outcome=Outcome.CREATED),
        ]
        records = cast("list[dict[str, str]]", outcomes_as_json(items)["items"])
        assert records[0]["group"] == "claude"
        assert "group" not in records[1]


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

    def test_unchanged_items_are_counted_but_not_listed(self, capsys):
        items = [
            OutcomeItem(name="changed.md", outcome=Outcome.CREATED),
            OutcomeItem(name="quiet-one.md", outcome=Outcome.UNCHANGED),
            OutcomeItem(name="quiet-two.md", outcome=Outcome.UNCHANGED),
        ]
        render_outcomes(items, title="Sync")
        out = capsys.readouterr().out
        assert "changed.md" in out
        # Unchanged files are folded into the count, never line-listed:
        # a result that names every untouched file is noise.
        assert "quiet-one.md" not in out
        assert "quiet-two.md" not in out
        assert "2 unchanged" in out
        assert "1 created" in out

    def test_grouped_items_render_under_sub_headings(self, capsys):
        items = [
            OutcomeItem(name="rule.md", outcome=Outcome.CREATED, group="claude"),
            OutcomeItem(name="quiet.md", outcome=Outcome.UNCHANGED, group="gemini"),
        ]
        render_outcomes(items, title="Sync")
        out = capsys.readouterr().out
        # A group with a real change gets a sub-heading + its items.
        assert "claude" in out
        assert "rule.md" in out
        # A group that is all-unchanged collapses to one acknowledgement.
        assert "gemini" in out
        assert "quiet.md" not in out
        assert "up to date" in out


@pytest.mark.unit
class TestSyncOutcomes:
    def test_action_log_maps_to_canonical_outcomes(self):
        result = SyncResult()
        result.items = [
            ("a.md", "[ADD]"),
            ("b.md", "[UPDATE]"),
            ("c.md", "[UNCHANGED]"),
            ("d.md", "[DELETE]"),
            ("e.md", "[SKIP]"),
        ]
        assert [o.outcome for o in sync_outcomes(result)] == [
            Outcome.CREATED,
            Outcome.UPDATED,
            Outcome.UNCHANGED,
            Outcome.REMOVED,
            Outcome.SKIPPED,
        ]

    def test_errors_become_failed_items_with_detail(self):
        result = SyncResult()
        result.errors = ["broken.md: transform exploded"]
        item = sync_outcomes(result)[0]
        assert item.outcome == Outcome.FAILED
        assert item.name == "broken.md"
        assert item.detail == "transform exploded"

    def test_empty_result_aggregates_to_unchanged(self):
        payload = outcomes_as_json(sync_outcomes(SyncResult()))
        assert payload["status"] == "unchanged"

    def test_group_label_propagates_to_every_item(self):
        result = SyncResult()
        result.items = [("a.md", "[ADD]")]
        result.errors = ["bad.md: transform exploded"]
        items = sync_outcomes(result, group="claude")
        assert items, "expected file and error items"
        assert all(item.group == "claude" for item in items)


@pytest.mark.unit
class TestEmitOutcomes:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_failed_outcome_forces_exit_code_one(self, capsys):
        items = [OutcomeItem(name="broken.md", outcome=Outcome.FAILED, detail="boom")]
        code = emit_outcomes(items, title="Sync", json_output=False)
        # A failed outcome is the one outcome that stops a pipeline.
        assert code == 1
        out = capsys.readouterr().out
        assert "broken.md" in out
        assert "boom" in out

    def test_no_failure_exits_zero(self, capsys):
        items = [
            OutcomeItem(name="a", outcome=Outcome.CREATED),
            OutcomeItem(name="b", outcome=Outcome.SKIPPED),
        ]
        assert emit_outcomes(items, title="Sync", json_output=False) == 0
        capsys.readouterr()

    def test_empty_invocation_exits_zero(self, capsys):
        assert emit_outcomes([], title="Sync", json_output=False) == 0
        capsys.readouterr()

    def test_json_envelope_merges_extra_keys(self, capsys):
        items = [OutcomeItem(name="a", outcome=Outcome.CREATED)]
        code = emit_outcomes(
            items,
            title="Sync",
            json_output=True,
            extra_json={"warnings": ["heads up"]},
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "created"
        assert payload["items"][0]["name"] == "a"
        assert payload["warnings"] == ["heads up"]

    def test_json_path_still_reports_failure_in_exit_code(self, capsys):
        items = [OutcomeItem(name="x", outcome=Outcome.FAILED)]
        code = emit_outcomes(items, title="Sync", json_output=True)
        assert code == 1
        assert json.loads(capsys.readouterr().out)["status"] == "failed"
