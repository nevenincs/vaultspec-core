"""Tests for the canonical outcome vocabulary in :mod:`cli.rendering`.

Covers the seven-word taxonomy, the aggregate rule, and the guarantee
that the text and JSON surfaces consume one :class:`OutcomeItem` list and
therefore cannot drift apart.
"""

from __future__ import annotations

import dataclasses
import json
from typing import ClassVar, cast

import pytest

from vaultspec_core.cli.rendering import (
    OUTCOME_STYLE,
    Cell,
    Column,
    Field,
    Outcome,
    OutcomeItem,
    TreeLine,
    aggregate_outcome,
    count_outcomes,
    emit_listing,
    emit_outcomes,
    emit_record,
    json_envelope,
    listing_as_json,
    outcomes_as_json,
    record_as_json,
    render_listing,
    render_outcomes,
    render_record,
    render_tree,
    summary_line,
    sync_outcomes,
    truncate,
)
from vaultspec_core.console import reset_console
from vaultspec_core.core.types import SyncResult


def _has_box_drawing(text: str) -> bool:
    """True if any Unicode box-drawing glyph (U+2500..U+257F) appears."""
    return any("─" <= ch <= "╿" for ch in text)


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
class TestJsonEnvelope:
    def test_wraps_payload_with_schema_and_status(self):
        env = json_envelope("sync", "updated", {"items": [1, 2]})
        assert env == {
            "schema": "vaultspec.sync.v1",
            "status": "updated",
            "data": {"items": [1, 2]},
        }

    def test_dotted_command_forms_namespaced_schema(self):
        env = json_envelope("spec.rules.sync", "unchanged", {})
        assert env["schema"] == "vaultspec.spec.rules.sync.v1"

    def test_hints_included_only_when_supplied(self):
        without = json_envelope("sync", "unchanged", {})
        assert "hints" not in without
        with_hint = json_envelope(
            "sync", "unchanged", {}, hints={"next_step": {"command": "x"}}
        )
        assert with_hint["hints"] == {"next_step": {"command": "x"}}


@pytest.mark.unit
class TestEmitOutcomes:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_failed_outcome_forces_exit_code_one(self, capsys):
        items = [OutcomeItem(name="broken.md", outcome=Outcome.FAILED, detail="boom")]
        code = emit_outcomes(items, command="sync", title="Sync", json_output=False)
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
        assert (
            emit_outcomes(items, command="sync", title="Sync", json_output=False) == 0
        )
        capsys.readouterr()

    def test_empty_invocation_exits_zero(self, capsys):
        assert emit_outcomes([], command="sync", title="Sync", json_output=False) == 0
        capsys.readouterr()

    def test_json_envelope_wraps_payload_with_extra_keys(self, capsys):
        items = [OutcomeItem(name="a", outcome=Outcome.CREATED)]
        code = emit_outcomes(
            items,
            command="sync",
            title="Sync",
            json_output=True,
            extra_json={"warnings": ["heads up"]},
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        # cli-json-consistency envelope: {schema, status, data}.
        assert payload["schema"] == "vaultspec.sync.v1"
        assert payload["status"] == "created"
        assert payload["data"]["items"][0]["name"] == "a"
        assert payload["data"]["warnings"] == ["heads up"]

    def test_json_path_still_reports_failure_in_exit_code(self, capsys):
        items = [OutcomeItem(name="x", outcome=Outcome.FAILED)]
        code = emit_outcomes(items, command="sync", title="Sync", json_output=True)
        assert code == 1
        assert json.loads(capsys.readouterr().out)["status"] == "failed"


@pytest.mark.unit
class TestTruncate:
    def test_value_within_budget_is_unchanged(self):
        assert truncate("short", 10) == "short"

    def test_value_over_budget_is_marked(self):
        out = truncate("a very long description indeed", 12)
        assert len(out) == 12
        assert out.endswith("...")
        assert out == "a very lo..."

    def test_budget_smaller_than_marker_degrades_gracefully(self):
        assert truncate("anything", 2) == ".."

    def test_truncation_is_width_independent(self):
        # Same input + same budget => same bytes, regardless of any console.
        assert truncate("x" * 100, 20) == truncate("x" * 100, 20)


@pytest.mark.unit
class TestSummaryLine:
    def test_count_and_noun(self):
        assert summary_line(3, "rules") == "3 rules"

    def test_breakdown_is_parenthesized(self):
        assert (
            summary_line(3, "rules", [(2, "project"), (1, "builtin")])
            == "3 rules (2 project, 1 builtin)"
        )

    def test_zero_count_breakdown_entries_are_dropped(self):
        assert summary_line(2, "rules", [(2, "project"), (0, "builtin")]) == (
            "2 rules (2 project)"
        )

    def test_caller_owns_singular_noun(self):
        assert summary_line(1, "rule") == "1 rule"


@pytest.mark.unit
class TestRecord:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_fields_render_as_key_value_lines(self, capsys):
        fields = [Field("status", "drifted"), Field("missing", "0")]
        render_record(fields, title="Rules status")
        out = capsys.readouterr().out
        assert "Rules status" in out
        assert "status: drifted" in out
        assert "missing: 0" in out
        assert not _has_box_drawing(out)

    def test_json_keys_equal_field_keys(self):
        fields = [Field("status", "ok"), Field("drifted", "none", style="yellow")]
        # Decorative style never reaches the machine surface.
        assert record_as_json(fields) == {"status": "ok", "drifted": "none"}

    def test_emit_record_json_envelope_shares_field_payload(self, capsys):
        fields = [Field("status", "ok")]
        emit_record(
            fields, command="spec.rules.status", title="Rules", json_output=True
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema"] == "vaultspec.spec.rules.status.v1"
        assert payload["data"]["status"] == "ok"

    def test_markup_in_values_does_not_break_rendering(self, capsys):
        render_record([Field("expr", "list[int]")], title="T")
        # A '[' in the value must survive as literal text, not a markup tag.
        assert "list[int]" in capsys.readouterr().out


@pytest.mark.unit
class TestListing:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    COLUMNS: ClassVar = [Column("name"), Column("source")]

    def test_rows_render_single_space_separated(self, capsys):
        rows = [
            {"name": "vaultspec-system", "source": "builtin"},
            {"name": "live-test", "source": "project"},
        ]
        render_listing(
            rows,
            self.COLUMNS,
            title="Rules",
            summary=summary_line(2, "rules", [(1, "project"), (1, "builtin")]),
        )
        out = capsys.readouterr().out
        assert "vaultspec-system builtin" in out
        assert "live-test project" in out
        assert "2 rules (1 project, 1 builtin)" in out
        assert not _has_box_drawing(out)

    def test_empty_listing_collapses_to_one_line(self, capsys):
        render_listing([], self.COLUMNS, title="Rules", empty="no rules")
        out = capsys.readouterr().out
        assert "no rules" in out
        assert not _has_box_drawing(out)

    def test_text_and_json_consume_one_column_order(self, capsys):
        rows = [{"name": "a", "source": "builtin"}]
        render_listing(rows, self.COLUMNS, title="Rules")
        text = capsys.readouterr().out
        payload = listing_as_json(rows, self.COLUMNS)
        # Both surfaces carry the same values under the same column identity.
        assert payload == [{"name": "a", "source": "builtin"}]
        assert "a builtin" in text

    def test_styled_cell_drops_style_in_json(self):
        rows = [{"name": "a", "source": Cell("builtin", style="dim")}]
        assert listing_as_json(rows, self.COLUMNS) == [
            {"name": "a", "source": "builtin"}
        ]

    def test_emit_listing_json_envelope_wraps_items(self, capsys):
        rows = [{"name": "a", "source": "builtin"}]
        emit_listing(
            rows,
            self.COLUMNS,
            command="spec.rules.list",
            title="Rules",
            json_output=True,
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema"] == "vaultspec.spec.rules.list.v1"
        assert payload["data"]["items"] == [{"name": "a", "source": "builtin"}]


@pytest.mark.unit
class TestRenderTree:
    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_depth_renders_as_indentation_not_connectors(self, capsys):
        lines = [
            TreeLine("feature-a", depth=0),
            TreeLine("plan.md", depth=1, glyph="+"),
        ]
        render_tree(lines, title="Graph")
        out = capsys.readouterr().out
        assert "Graph" in out
        assert "feature-a" in out
        assert "+ plan.md" in out
        # Hierarchy is indentation only - never box-drawing connectors.
        assert not _has_box_drawing(out)

    def test_deeper_nodes_indent_further(self, capsys):
        render_tree([TreeLine("root", depth=0), TreeLine("child", depth=2)], title="T")
        lines = capsys.readouterr().out.splitlines()
        root_line = next(line for line in lines if "root" in line)
        child_line = next(line for line in lines if "child" in line)
        assert len(child_line) - len(child_line.lstrip()) > (
            len(root_line) - len(root_line.lstrip())
        )
