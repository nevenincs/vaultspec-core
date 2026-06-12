"""Integration tests for the ``vault status`` CLI verb.

Implements the verification surface for the vault-orientation ADR's
decisions D1, D2, D4, D5, and D7: the rollup mode lists in-flight plans
with open/closed counts and renders documents as stems only; ``--limit``
and ``--since`` change the recent set; the trace mode maps a checked step
to its execution-record stem and reports an open step as having no
record; an unknown target exits 1 naming near-matches; ``--json`` matches
the versioned envelope and carries hints; and hint lines appear in human
output unless suppressed.

Every test drives the real Typer application through ``CliRunner``
against genuine ``.vault/`` documents on the filesystem. There are no
mocks, patches, stubs, or skips: the verb reads real files and the
assertions read the verb's real output. Documents carry deliberately
distinct, stale ``modified:`` stamps so recency ordering and windowing
are observable, non-tautological facts.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


def _run(root: Path, *args: str):
    """Invoke ``vault status`` against *root* via the root ``-t`` target."""
    runner = CliRunner(env={"NO_COLOR": "1"})
    return runner.invoke(app, ["-t", str(root), "vault", "status", *args])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plan(
    feature: str,
    *,
    date: str,
    modified: str,
    steps: list[tuple[str, bool]],
    related: list[str] | None = None,
) -> str:
    """Render an L2 plan with one phase of explicit step rows."""
    lines = [
        "---",
        "tags:",
        "  - '#plan'",
        f"  - '#{feature}'",
        f"date: '{date}'",
        f"modified: '{modified}'",
        "tier: L2",
    ]
    if related:
        lines.append("related:")
        lines += [f"  - '[[{r}]]'" for r in related]
    else:
        lines.append("related: []")
    lines += [
        "---",
        "",
        f"# `{feature}` plan",
        "",
        f"{feature} plan body.",
        "",
        "## Phase `P01` - Build",
        "",
        "Phase intent.",
        "",
    ]
    for step_id, checked in steps:
        box = "x" if checked else " "
        lines.append(f"- [{box}] `P01.{step_id}` - do the work; `src/{step_id}.py`.")
    lines.append("")
    return "\n".join(lines)


def _exec(
    feature: str,
    *,
    date: str,
    modified: str,
    step_id: str | None,
    plan_stem: str,
) -> str:
    """Render an execution record, optionally carrying a ``step_id:``."""
    lines = [
        "---",
        "tags:",
        "  - '#exec'",
        f"  - '#{feature}'",
        f"date: '{date}'",
        f"modified: '{modified}'",
    ]
    if step_id is not None:
        lines.append(f"step_id: '{step_id}'")
    lines += [
        "related:",
        f"  - '[[{plan_stem}]]'",
        "---",
        "",
        "Execution details.",
        "",
    ]
    return "\n".join(lines)


def _grounding(
    doc_type: str,
    feature: str,
    *,
    date: str,
    modified: str,
    related: list[str] | None = None,
) -> str:
    """Render a non-plan grounding document (adr, research, reference)."""
    lines = [
        "---",
        "tags:",
        f"  - '#{doc_type}'",
        f"  - '#{feature}'",
        f"date: '{date}'",
        f"modified: '{modified}'",
    ]
    if related:
        lines.append("related:")
        lines += [f"  - '[[{r}]]'" for r in related]
    else:
        lines.append("related: []")
    lines += ["---", "", f"# {feature} {doc_type}", "", "Body.", ""]
    return "\n".join(lines)


def _build_vault(root: Path) -> dict[str, str]:
    """Build one feature vault: research, adr, a plan, and three execs.

    The plan ``S01`` and ``S02`` are closed with matching records, ``S03``
    is open with no record, and one extra exec references the plan without
    a ``step_id:`` (the unlinked bucket). The plan's recency stamp is the
    most recent date so the rollup lists it.
    """
    vault = root / ".vault"
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)

    feature = "widget"
    plan_stem = f"2026-03-01-{feature}-plan"
    adr_stem = f"2026-02-20-{feature}-adr"
    research_stem = f"2026-02-10-{feature}-research"

    _write(
        vault / "research" / f"{research_stem}.md",
        _grounding("research", feature, date="2026-02-10", modified="2026-02-10"),
    )
    _write(
        vault / "adr" / f"{adr_stem}.md",
        _grounding(
            "adr",
            feature,
            date="2026-02-20",
            modified="2026-02-20",
            related=[research_stem],
        ),
    )
    _write(
        vault / "plan" / f"{plan_stem}.md",
        _plan(
            feature,
            date="2026-03-01",
            modified="2026-03-15",
            steps=[("S01", True), ("S02", True), ("S03", False)],
            related=[adr_stem, research_stem],
        ),
    )
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-P01-S01.md",
        _exec(
            feature,
            date="2026-03-02",
            modified="2026-03-02",
            step_id="S01",
            plan_stem=plan_stem,
        ),
    )
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-P01-S02.md",
        _exec(
            feature,
            date="2026-03-10",
            modified="2026-03-10",
            step_id="S02",
            plan_stem=plan_stem,
        ),
    )
    _write(
        vault / "exec" / f"2026-03-01-{feature}" / f"2026-03-01-{feature}-orphan.md",
        _exec(
            feature,
            date="2026-03-12",
            modified="2026-03-12",
            step_id=None,
            plan_stem=plan_stem,
        ),
    )

    return {
        "feature": feature,
        "plan": plan_stem,
        "adr": adr_stem,
        "research": research_stem,
        "exec_s01": f"2026-03-01-{feature}-P01-S01",
        "exec_orphan": f"2026-03-01-{feature}-orphan",
    }


# ---------------------------------------------------------------------------
# Rollup mode (decisions D2 / D4 / D7)
# ---------------------------------------------------------------------------


class TestRollup:
    """The no-argument rollup lists in-flight plans as stems plus hints."""

    def test_lists_in_flight_plan_with_counts(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path)

        assert result.exit_code == 0, result.output
        assert "Plans in flight" in result.output
        assert ids["plan"] in result.output
        # Two closed of three total, one open: counts are rendered.
        assert "2/3 done" in result.output
        assert "1 open" in result.output

    def test_renders_stems_only_no_absolute_paths(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path)

        assert result.exit_code == 0, result.output
        # Stems appear; no absolute filesystem path leaks into the output.
        assert ids["plan"] in result.output
        assert ids["research"] in result.output
        assert str(tmp_path) not in result.output
        assert ".vault" not in result.output
        # No path-shaped tokens: a stem like "exec/2026-..." or a backslash
        # path would betray a leaked file path. The completion fraction
        # "2/3" is the only legitimate slash, so assert on the path
        # segments that would accompany a real path instead.
        assert ".md" not in result.output
        assert "exec/" not in result.output
        assert "\\" not in result.output

    def test_limit_narrows_the_recent_set(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        # Limit of 1 keeps only the single most-recent document: the plan
        # (modified 2026-03-15), dropping the older research document.
        result = _run(tmp_path, "--limit", "1")

        assert result.exit_code == 0, result.output
        # The plan stem still appears under "Plans in flight" regardless,
        # so assert on a recency-only document instead: research is older
        # than the top document and must be excluded from the recent set.
        recent_section = result.output.split("Active features")[0]
        recent_block = recent_section.split("Recent changes")[1]
        assert ids["research"] not in recent_block

    def test_since_window_filters_by_day_distance(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)
        # The newest document is the plan at 2026-03-15. A 5-day window
        # anchored on the plan date keeps the plan and excludes the
        # 2026-02-10 research document. The verb anchors --since on today,
        # so seed today far in the future relative to the fixtures by using
        # a window wide enough to include all, then a narrow one to exclude.
        wide = _run(tmp_path, "--since", "100000")
        narrow = _run(tmp_path, "--since", "1")

        assert wide.exit_code == 0, wide.output
        assert narrow.exit_code == 0, narrow.output
        wide_recent = wide.output.split("Active features")[0]
        narrow_recent = narrow.output.split("Active features")[0]
        # The wide window includes the old research document; the 1-day
        # window (all fixtures predate today) excludes everything recent.
        assert ids["research"] in wide_recent
        assert ids["research"] not in narrow_recent

    def test_hints_present_in_human_output(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path)

        assert result.exit_code == 0, result.output
        assert "Suggested Next Step" in result.output
        assert "vaultspec-core vault status" in result.output
        assert "vaultspec-core spec doctor" in result.output

    def test_no_hints_suppresses_hint_block(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path, "--no-hints")

        assert result.exit_code == 0, result.output
        assert "Suggested Next Step" not in result.output

    def test_json_envelope_shape(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, "--json")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["schema"] == "vaultspec.vault.status.v1"
        assert payload["status"] == "unchanged"
        data = payload["data"]
        plan_stems = [p["stem"] for p in data["plans_in_flight"]]
        assert ids["plan"] in plan_stems
        in_flight = next(p for p in data["plans_in_flight"] if p["stem"] == ids["plan"])
        assert in_flight["open_steps"] == 1
        assert in_flight["closed_steps"] == 2
        assert in_flight["total_steps"] == 3
        assert "hints" in payload
        commands = [h["command"] for h in payload["hints"]["next_steps"]]
        assert any("vault status" in c for c in commands)
        assert any("spec doctor" in c for c in commands)


# ---------------------------------------------------------------------------
# Trace mode (decisions D1 / D5 / D7)
# ---------------------------------------------------------------------------


class TestTrace:
    """A target argument renders the grounding trace for that target."""

    def test_checked_step_maps_to_record_stem(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        assert "Grounding Trace" in result.output
        # The closed S01 step is mapped to its execution-record stem.
        assert ids["exec_s01"] in result.output

    def test_open_step_renders_no_record(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        # S03 is open and has no execution record.
        s03_line = next(
            line for line in result.output.splitlines() if "P01.S03" in line
        )
        assert "no record" in s03_line

    def test_unlinked_record_is_reported(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        assert "unlinked records" in result.output
        assert ids["exec_orphan"] in result.output

    def test_grounding_documents_grouped_by_type(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        assert "grounding" in result.output
        assert ids["adr"] in result.output
        assert ids["research"] in result.output

    def test_renders_stems_only_no_absolute_paths(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        assert str(tmp_path) not in result.output
        assert ".vault" not in result.output

    def test_unknown_target_exits_1_with_near_matches(self, tmp_path: Path) -> None:
        _build_vault(tmp_path)

        # 'widg' is a substring of the 'widget' feature and plan stem, so
        # the error must name the near-matches.
        result = _run(tmp_path, "widg")

        assert result.exit_code == 1, result.output
        assert "Could not resolve" in result.output
        assert "Did you mean" in result.output
        assert "widget" in result.output

    def test_hints_present_in_human_output(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"])

        assert result.exit_code == 0, result.output
        assert "Suggested Next Step" in result.output
        assert f"vaultspec-core vault graph --feature {ids['feature']}" in result.output
        assert "vaultspec-core vault plan status" in result.output

    def test_json_envelope_shape(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)

        result = _run(tmp_path, ids["plan"], "--json")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["schema"] == "vaultspec.vault.status.v1"
        assert payload["status"] == "unchanged"
        data = payload["data"]
        assert data["target"] == ids["plan"]
        assert data["kind"] == "plan"
        plan = data["plans"][0]
        assert plan["stem"] == ids["plan"]
        s01 = next(s for s in plan["steps"] if s["canonical_id"] == "S01")
        assert s01["record_stem"] == ids["exec_s01"]
        assert s01["checked"] is True
        s03 = next(s for s in plan["steps"] if s["canonical_id"] == "S03")
        assert s03["record_stem"] is None
        assert s03["checked"] is False
        assert ids["exec_orphan"] in plan["unlinked_records"]
        assert "hints" in payload
        commands = [h["command"] for h in payload["hints"]["next_steps"]]
        assert any("vault graph" in c for c in commands)
        assert any("vault plan status" in c for c in commands)


# ---------------------------------------------------------------------------
# Human-review refinements (post-verify sign-off pass)
# ---------------------------------------------------------------------------


class TestReviewRefinements:
    """Refinements applied after the human interface review.

    Phase summaries group under their own heading instead of the unlinked
    bucket, the active-features listing is capped in human output, and an
    unresolvable target with no near-matches points at the feature list.
    """

    def test_phase_summary_grouped_not_unlinked(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)
        feature = ids["feature"]
        summary_stem = f"2026-03-01-{feature}-P01-summary"
        _write(
            tmp_path
            / ".vault"
            / "exec"
            / f"2026-03-01-{feature}"
            / f"{summary_stem}.md",
            _exec(
                feature,
                date="2026-03-14",
                modified="2026-03-14",
                step_id=None,
                plan_stem=ids["plan"],
            ),
        )

        result = _run(tmp_path, ids["plan"], "--json")

        assert result.exit_code == 0, result.output
        plan = json.loads(result.output)["data"]["plans"][0]
        assert summary_stem in plan["summaries"]
        assert summary_stem not in plan["unlinked_records"]
        # The genuinely unlinked record stays in its bucket.
        assert ids["exec_orphan"] in plan["unlinked_records"]

        human = _run(tmp_path, ids["plan"])
        assert "summaries" in human.output
        assert summary_stem in human.output

    def test_unknown_target_without_near_matches_points_to_feature_list(
        self, tmp_path: Path
    ) -> None:
        _build_vault(tmp_path)

        result = _run(tmp_path, "zzz-no-such-target-qqq")

        assert result.exit_code == 1, result.output
        assert "Could not resolve" in result.output
        assert "Did you mean" not in result.output
        assert "vaultspec-core vault feature list" in result.output

    def test_active_features_capped_in_human_output(self, tmp_path: Path) -> None:
        ids = _build_vault(tmp_path)
        # Twelve extra single-document features push the total past the
        # ten-feature display cap.
        for n in range(12):
            feature = f"filler-{n:02d}"
            _write(
                tmp_path / ".vault" / "research" / f"2026-01-01-{feature}-research.md",
                _grounding(
                    "research", feature, date="2026-01-01", modified="2026-01-01"
                ),
            )

        result = _run(tmp_path)

        assert result.exit_code == 0, result.output
        assert "more" in result.output
        assert "vaultspec-core vault feature list" in result.output

        payload = json.loads(_run(tmp_path, "--json").output)
        features = payload["data"]["active_features"]
        # The JSON payload stays uncapped: 12 fillers plus the widget feature.
        assert len(features) == 13
        assert ids["feature"] in {f["name"] for f in features}
