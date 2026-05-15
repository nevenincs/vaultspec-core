"""Structure fixer tests for case-only filename normalization."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ...models import DocumentMetadata
from ..structure import check_structure

if TYPE_CHECKING:
    from pathlib import Path

    from .._base import VaultSnapshot

pytestmark = [pytest.mark.unit]


def _write_doc(path: Path, tags: list[str], related: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    related_yaml = "\n".join(f"  - '[[{target}]]'" for target in related)
    related_block = f"related:\n{related_yaml}" if related else "related: []"
    path.write_text(
        "---\n"
        "tags:\n"
        + "".join(f"  - '{tag}'\n" for tag in tags)
        + "date: '2026-05-15'\n"
        + related_block
        + "\n---\n\n# Test\n",
        encoding="utf-8",
    )


def test_fix_lowercases_case_drift_and_rewrites_related(tmp_path: Path) -> None:
    root = tmp_path
    upper = root / ".vault" / "research" / "2026-05-15-Repair-Case-research.md"
    lower = root / ".vault" / "research" / "2026-05-15-repair-case-research.md"
    plan = root / ".vault" / "plan" / "2026-05-15-repair-case-plan.md"
    old_stem = "2026-05-15-Repair-Case-research"
    new_stem = "2026-05-15-repair-case-research"

    _write_doc(upper, ["#research", "#repair-case"], [])
    _write_doc(plan, ["#plan", "#repair-case"], [old_stem])

    snapshot: VaultSnapshot = {
        upper: (
            DocumentMetadata(
                tags=["#research", "#repair-case"],
                date="2026-05-15",
                related=[],
            ),
            "",
        ),
        plan: (
            DocumentMetadata(
                tags=["#plan", "#repair-case"],
                date="2026-05-15",
                related=[f"[[{old_stem}]]"],
            ),
            "",
        ),
    }

    result = check_structure(root, snapshot=snapshot, fix=True)

    assert result.error_count == 0
    assert any(path.name == lower.name for path in lower.parent.iterdir())
    assert f"[[{new_stem}]]" in plan.read_text(encoding="utf-8")
