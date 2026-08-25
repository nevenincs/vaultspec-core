"""Tests for the features vault health checker.

Covers the document-type coverage rules, with emphasis on the grounding a
plan actually declares. A plan may execute an ADR that belongs to another
feature - the sanctioned cluster and roll-up shape - so ADR backing cannot be
judged by feature-tag co-membership alone. No mocks, patches, or skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....graph import VaultGraph
from ..features import check_features

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _write_doc(
    root: Path,
    doc_type: str,
    stem: str,
    feature: str,
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
        f"  - '#{feature}'\n"
        "date: '2026-02-04'\n"
        "modified: '2026-02-04'\n"
        f"{related_yaml}"
        "---\n"
        f"\n# {stem}\n",
        encoding="utf-8",
    )


def _plan_backing_diagnostics(root: Path) -> list[str]:
    snapshot = VaultGraph(root).to_snapshot()
    result = check_features(root, snapshot=snapshot)
    return [d.message for d in result.diagnostics if "but no ADR" in d.message]


class TestPlanAdrBacking:
    def test_plan_without_any_adr_is_reported(self, tmp_path: Path) -> None:
        _write_doc(tmp_path, "plan", "2026-02-04-lonely-plan", "lonely")

        messages = _plan_backing_diagnostics(tmp_path)

        assert len(messages) == 1
        assert "lonely" in messages[0]

    def test_same_feature_adr_backs_the_plan(self, tmp_path: Path) -> None:
        _write_doc(tmp_path, "adr", "2026-02-04-paired-adr", "paired")
        _write_doc(tmp_path, "plan", "2026-02-04-paired-plan", "paired")

        assert _plan_backing_diagnostics(tmp_path) == []

    def test_cross_feature_adr_named_in_related_backs_the_plan(
        self, tmp_path: Path
    ) -> None:
        """The cluster shape: the governing ADR carries another feature tag."""
        _write_doc(tmp_path, "adr", "2026-02-04-governing-adr", "governing")
        _write_doc(
            tmp_path,
            "plan",
            "2026-02-04-sweep-plan",
            "sweep",
            related=["2026-02-04-governing-adr"],
        )

        assert _plan_backing_diagnostics(tmp_path) == []

    def test_related_link_to_a_non_adr_does_not_back_the_plan(
        self, tmp_path: Path
    ) -> None:
        """Only an ADR satisfies ADR backing, whatever else is cited."""
        _write_doc(tmp_path, "audit", "2026-02-04-governing-audit", "governing")
        _write_doc(
            tmp_path,
            "plan",
            "2026-02-04-sweep-plan",
            "sweep",
            related=["2026-02-04-governing-audit"],
        )

        messages = _plan_backing_diagnostics(tmp_path)

        assert len(messages) == 1
        assert "sweep" in messages[0]
