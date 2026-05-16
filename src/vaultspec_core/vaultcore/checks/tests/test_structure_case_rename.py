"""Structure fixer tests for case-only filename normalization."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config

from ...models import DocumentMetadata
from ..structure import _fix_filename, _rename_document_path, check_structure

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


def test_fix_rewrites_related_in_configured_docs_dir(tmp_path: Path) -> None:
    old_docs_dir = os.environ.get("VAULTSPEC_DOCS_DIR")
    os.environ["VAULTSPEC_DOCS_DIR"] = "notes"
    reset_config()
    try:
        root = tmp_path
        upper = root / "notes" / "research" / "2026-05-15-Repair-Case-research.md"
        lower = root / "notes" / "research" / "2026-05-15-repair-case-research.md"
        plan = root / "notes" / "plan" / "2026-05-15-repair-case-plan.md"
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
        assert lower.exists()
        assert f"[[{new_stem}]]" in plan.read_text(encoding="utf-8")
    finally:
        if old_docs_dir is None:
            os.environ.pop("VAULTSPEC_DOCS_DIR", None)
        else:
            os.environ["VAULTSPEC_DOCS_DIR"] = old_docs_dir
        reset_config()


def test_case_only_rename_uses_short_temp_name_for_long_filenames(
    tmp_path: Path,
) -> None:
    docs = tmp_path / ".vault" / "research"
    docs.mkdir(parents=True)
    long_feature = "A" * 190
    source = docs / f"2026-05-15-{long_feature}-research.md"
    target = source.with_name(source.name.lower())
    source.write_text("# Long case-only rename\n", encoding="utf-8")

    assert len(source.name) < 255
    assert _rename_document_path(source, target) is True
    assert target.exists()
    assert source.name not in {path.name for path in docs.iterdir()}
    assert not list(docs.glob(".vs-*.tmp"))


def test_fix_filename_reports_final_path_after_multi_step_rename(
    tmp_path: Path,
) -> None:
    source = tmp_path / ".vault" / "research" / "2026-05-15-Repair-Case.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Repair case\n", encoding="utf-8")

    from .._base import CheckResult

    result = CheckResult(check_name="structure", supports_fix=True)

    renames, final_path = _fix_filename(source, tmp_path, result)

    assert final_path == (
        tmp_path / ".vault" / "research" / "2026-05-15-repair-case-research.md"
    )
    assert final_path.exists()
    assert len(renames) == 2
    assert result.fixed_count == 2
    assert [diag.path for diag in result.diagnostics] == [
        final_path.relative_to(tmp_path),
        final_path.relative_to(tmp_path),
    ]
