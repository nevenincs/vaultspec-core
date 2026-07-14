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
        f"  - '#{_FEATURE}'\n"
        "date: '2026-07-14'\n"
        f"{related_yaml}"
        "---\n"
        f"\n# {stem}\n",
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


class TestAdrGroundingFix:
    """The fix path links the best available grounding candidate."""

    def test_fix_prefers_research(self, tmp_path: Path):
        _write_doc(tmp_path, "research", "2026-07-14-grounding-feat-research")
        _write_doc(tmp_path, "audit", "2026-07-14-grounding-feat-audit")
        _write_doc(tmp_path, "adr", "2026-07-14-grounding-feat-adr")

        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)

        assert result.fixed_count == 1
        adr = (
            tmp_path / ".vault" / "adr" / "2026-07-14-grounding-feat-adr.md"
        ).read_text(encoding="utf-8")
        assert "[[2026-07-14-grounding-feat-research]]" in adr

    def test_fix_falls_back_to_audit(self, tmp_path: Path):
        _write_doc(tmp_path, "audit", "2026-07-14-grounding-feat-audit")
        _write_doc(tmp_path, "adr", "2026-07-14-grounding-feat-adr")

        result = check_schema(tmp_path, graph=VaultGraph(tmp_path), fix=True)

        assert result.fixed_count == 1
        adr = (
            tmp_path / ".vault" / "adr" / "2026-07-14-grounding-feat-adr.md"
        ).read_text(encoding="utf-8")
        assert "[[2026-07-14-grounding-feat-audit]]" in adr
