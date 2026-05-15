"""Tests for explicit template annotation sanitization."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ..annotations import check_annotations, strip_template_annotations

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _write_doc(
    root: Path,
    feature: str,
    content: str,
    *,
    doc_type: str = "research",
) -> Path:
    path = root / ".vault" / doc_type / f"2026-05-15-{feature}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _annotated_doc(feature: str) -> str:
    return (
        "---\n"
        "# Required tag guidance\n"
        "tags:\n"
        "  - '#research'\n"
        f"  - '#{feature}'\n"
        "# Date guidance\n"
        "date: '2026-05-15'\n"
        "related: []\n"
        "---\n"
        "\n"
        "<!-- FRONTMATTER RULES:\n"
        "     Fill this generated scaffold before committing. -->\n"
        "\n"
        f"# {feature} research\n"
        "\n"
        "```html\n"
        "<!-- This code example is not a template annotation. -->\n"
        "```\n"
        "\n"
        "Mention `<!-- inline example -->` in prose.\n"
        "<!-- RETIRED: S01 -->\n"
    )


def test_check_reports_annotations_without_mutating(tmp_path: Path) -> None:
    doc = _write_doc(tmp_path, "annotation-report", _annotated_doc("annotation-report"))
    before = doc.read_text(encoding="utf-8")

    result = check_annotations(tmp_path)

    after = doc.read_text(encoding="utf-8")
    assert result.check_name == "annotations"
    assert result.warning_count == 1
    assert result.fixed_count == 0
    assert result.diagnostics[0].fixable is True
    assert "frontmatter comment line" in result.diagnostics[0].message
    assert "HTML comment block" in result.diagnostics[0].message
    assert after == before


def test_fix_strips_annotations_but_preserves_code_examples(tmp_path: Path) -> None:
    doc = _write_doc(tmp_path, "annotation-fix", _annotated_doc("annotation-fix"))

    result = check_annotations(tmp_path, fix=True)

    cleaned = doc.read_text(encoding="utf-8")
    assert result.fixed_count == 1
    assert "# Required tag guidance" not in cleaned
    assert "<!-- FRONTMATTER RULES:" not in cleaned
    assert "# annotation-fix research" in cleaned
    assert "<!-- This code example is not a template annotation. -->" in cleaned
    assert "`<!-- inline example -->`" in cleaned
    assert "<!-- RETIRED: S01 -->" in cleaned


def test_dry_run_reports_planned_strips_without_mutating(tmp_path: Path) -> None:
    doc = _write_doc(
        tmp_path, "annotation-dry-run", _annotated_doc("annotation-dry-run")
    )
    before = doc.read_text(encoding="utf-8")

    result = check_annotations(tmp_path, fix=True, dry_run=True)

    assert result.fixed_count == 0
    assert result.warning_count == 1
    assert "Would remove template annotations" in result.diagnostics[0].message
    assert doc.read_text(encoding="utf-8") == before


def test_feature_filter_only_strips_matching_documents(tmp_path: Path) -> None:
    target = _write_doc(
        tmp_path, "matching-feature", _annotated_doc("matching-feature")
    )
    other = _write_doc(tmp_path, "other-feature", _annotated_doc("other-feature"))

    result = check_annotations(tmp_path, feature="matching-feature", fix=True)

    assert result.fixed_count == 1
    assert "<!-- FRONTMATTER RULES:" not in target.read_text(encoding="utf-8")
    assert "<!-- FRONTMATTER RULES:" in other.read_text(encoding="utf-8")


def test_strip_template_annotations_preserves_crlf() -> None:
    source = _annotated_doc("newline-feature").replace("\n", "\r\n")

    cleaned_lf, stats = strip_template_annotations(source)
    cleaned = cleaned_lf.replace("\n", "\r\n")

    assert stats.total == 3
    assert "\r\n" in cleaned
    assert "\n<!-- FRONTMATTER RULES:" not in cleaned
