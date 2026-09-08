"""Schema check: ADR grounding accepts the sanctioned document types.

The documentation hierarchy sanctions research, reference, and audit
documents as ADR grounding, so `check_schema` must accept any one of the
three and error only when none is linked. All tests run against real
on-disk vault fixtures (no mocks).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.graph.api import VaultGraph
from vaultspec_core.vaultcore.checks.references import check_schema

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_FEATURE = "grounding-feat"


def _write_doc(
    root: Path,
    doc_type: str,
    stem: str,
    *,
    related: list[str] | None = None,
    body: str | None = None,
    feature: str = _FEATURE,
) -> None:
    doc_dir = root / ".vault" / doc_type
    doc_dir.mkdir(parents=True, exist_ok=True)
    related_yaml = (
        "related: []\n"
        if not related
        else "related:\n" + "".join(f"  - '[[{r}]]'\n" for r in related)
    )
    (doc_dir / f"{stem}.md").write_text(
        "---\n"
        "tags:\n"
        f"  - '#{doc_type}'\n"
        f"  - '#{feature}'\n"
        "date: '2026-07-14'\n"
        f"{related_yaml}"
        "---\n" + (body if body is not None else f"\n# {stem}\n"),
        encoding="utf-8",
    )


def _adr_diagnostics(root: Path) -> list[str]:
    result = check_schema(root, graph=VaultGraph(root))
    return [
        d.message
        for d in result.diagnostics
        if "ADR has no grounding references" in d.message
    ]


class TestAdrGroundingAcceptance:
    """Any sanctioned grounding type satisfies the ADR schema check."""

    def test_research_grounding_passes(self, tmp_path: Path):
        _write_doc(tmp_path, "research", "2026-07-14-grounding-feat-research")
        _write_doc(
            tmp_path,
            "adr",
            "2026-07-14-grounding-feat-adr",
            related=["2026-07-14-grounding-feat-research"],
        )
        assert _adr_diagnostics(tmp_path) == []

    def test_reference_grounding_passes(self, tmp_path: Path):
        _write_doc(tmp_path, "reference", "2026-07-14-grounding-feat-reference")
        _write_doc(
            tmp_path,
            "adr",
            "2026-07-14-grounding-feat-adr",
            related=["2026-07-14-grounding-feat-reference"],
        )
        assert _adr_diagnostics(tmp_path) == []

    def test_audit_grounding_passes(self, tmp_path: Path):
        _write_doc(tmp_path, "audit", "2026-07-14-grounding-feat-audit")
        _write_doc(
            tmp_path,
            "adr",
            "2026-07-14-grounding-feat-adr",
            related=["2026-07-14-grounding-feat-audit"],
        )
        assert _adr_diagnostics(tmp_path) == []

    def test_ungrounded_adr_errors(self, tmp_path: Path):
        _write_doc(tmp_path, "adr", "2026-07-14-grounding-feat-adr")
        messages = _adr_diagnostics(tmp_path)
        assert len(messages) == 1
        assert "research, reference, or audit" in messages[0]

    def test_plan_link_alone_does_not_ground(self, tmp_path: Path):
        _write_doc(tmp_path, "plan", "2026-07-14-grounding-feat-plan")
        _write_doc(
            tmp_path,
            "adr",
            "2026-07-14-grounding-feat-adr",
            related=["2026-07-14-grounding-feat-plan"],
        )
        assert len(_adr_diagnostics(tmp_path)) == 1


class TestPlanDecisionCoverage:
    """Assess complete plan routes without guessing authority from feature tags."""

    @pytest.mark.parametrize("evidence", ["research", "reference", "audit"])
    def test_repair_does_not_select_evidence(self, tmp_path: Path, evidence: str):
        _write_doc(tmp_path, evidence, "evidence")
        _write_doc(tmp_path, "adr", "decision")
        path = tmp_path / ".vault" / "adr" / "decision.md"
        before = path.read_bytes()
        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)
        assert result.fixed_count == 0
        assert path.read_bytes() == before
        assert any("ADR has no grounding" in d.message for d in result.diagnostics)
        assert all(not d.fixable for d in result.diagnostics)

    def test_decision_free_plan_survives_check_and_repair(self, tmp_path: Path):
        _write_doc(tmp_path, "plan", "mechanical", body=_plan_body())
        path = tmp_path / ".vault" / "plan" / "mechanical.md"
        before = path.read_bytes()
        for fix in (False, True):
            result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=fix)
            assert result.diagnostics == []
            assert result.fixed_count == 0
        assert path.read_bytes() == before

    @pytest.mark.parametrize("evidence", ["research", "reference", "audit"])
    def test_cross_feature_reuse_inherits_evidence(self, tmp_path: Path, evidence: str):
        _write_doc(tmp_path, evidence, "evidence")
        _write_doc(
            tmp_path,
            "adr",
            "decision",
            related=["evidence"],
            body="# Decision | (**status:** `accepted`)\n",
            feature="shared",
        )
        for name in ("first-plan", "second-plan"):
            _write_doc(tmp_path, "plan", name, related=["decision"], body=_plan_body())
        before = {p: p.read_bytes() for p in (tmp_path / ".vault").rglob("*.md")}
        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)
        assert result.diagnostics == []
        assert {p: p.read_bytes() for p in before} == before

    @pytest.mark.parametrize(
        "status", ["proposed", "rejected", "deprecated", "superseded", ""]
    )
    @pytest.mark.parametrize("state", ["draft", "active", "complete"])
    def test_authority_depends_on_plan_state(
        self, tmp_path: Path, status: str, state: str
    ):
        _write_doc(tmp_path, "audit", "evidence")
        _write_doc(
            tmp_path,
            "adr",
            "decision",
            related=["evidence"],
            body=f"# Decision | (**status:** `{status}`)\n",
        )
        _write_doc(
            tmp_path,
            "plan",
            "work",
            related=["decision"],
            body=_plan_body(approved=state != "draft", closed=state == "complete"),
        )
        result = check_schema(tmp_path, graph=VaultGraph(tmp_path))
        failures = [d for d in result.diagnostics if "non-accepted ADR" in d.message]
        assert bool(failures) == (state == "active")

    def test_completed_plan_reopened_rechecks_authority(self, tmp_path: Path):
        _write_doc(tmp_path, "audit", "evidence")
        _write_doc(
            tmp_path,
            "adr",
            "decision",
            related=["evidence"],
            body="# Decision | (**status:** `superseded`)\n",
        )
        _write_doc(
            tmp_path, "plan", "work", related=["decision"], body=_plan_body(closed=True)
        )
        assert check_schema(tmp_path, graph=VaultGraph(tmp_path)).diagnostics == []
        _write_doc(tmp_path, "plan", "work", related=["decision"], body=_plan_body())
        result = check_schema(tmp_path, graph=VaultGraph(tmp_path))
        assert any("non-accepted ADR" in d.message for d in result.diagnostics)


def _plan_body(*, approved: bool = True, closed: bool = False) -> str:
    approval = "Approved 2026-09-08\n\n" if approved else ""
    state = "x" if closed else " "
    return (
        "# Work\n\n## Description\n\n"
        + approval
        + (
            "Mechanical changes within existing constraints; no costly decision is "
            "involved.\n\n"
        )
        + f"## Steps\n\n- [{state}] `S01` - Update the messages; `src/messages`.\n"
    )
