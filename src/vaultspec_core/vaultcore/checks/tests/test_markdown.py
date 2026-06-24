"""Tests for the markdown hygiene checker."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ..markdown import apply_markdown_hygiene, check_markdown

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _write_doc(root: Path, feature: str, content: str) -> Path:
    path = root / ".vault" / "research" / f"2026-06-24-{feature}-research.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _doc(feature: str, body: str) -> str:
    return (
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        f"  - '#{feature}'\n"
        "date: '2026-06-24'\n"
        "related: []\n"
        "---\n"
        "\n" + body
    )


class TestApplyMarkdownHygiene:
    def test_strips_trailing_whitespace(self):
        cleaned, stats = apply_markdown_hygiene("line one   \nline two\t\n")
        assert cleaned == "line one\nline two\n"
        assert stats.trailing_whitespace == 2

    def test_collapses_consecutive_blank_lines(self):
        cleaned, stats = apply_markdown_hygiene("a\n\n\n\nb\n")
        assert cleaned == "a\n\nb\n"
        assert stats.blank_runs == 2

    def test_adds_missing_final_newline(self):
        cleaned, stats = apply_markdown_hygiene("a\nb")
        assert cleaned == "a\nb\n"
        assert stats.final_newline is True

    def test_collapses_trailing_blank_lines_to_single_newline(self):
        cleaned, _stats = apply_markdown_hygiene("a\nb\n\n\n")
        assert cleaned == "a\nb\n"

    def test_preserves_whitespace_inside_fenced_code(self):
        body = "text\n\n```\ncode   \n\n\nmore\n```\n"
        cleaned, stats = apply_markdown_hygiene(body)
        assert "code   \n" in cleaned
        assert "\n\n\nmore" in cleaned
        assert stats.trailing_whitespace == 0
        assert stats.blank_runs == 0

    def test_idempotent(self):
        once, _ = apply_markdown_hygiene("a   \n\n\n\nb\n\n\n")
        twice, stats = apply_markdown_hygiene(once)
        assert twice == once
        assert stats.total == 0

    def test_clean_content_unchanged(self):
        clean = "a\n\nb\n"
        cleaned, stats = apply_markdown_hygiene(clean)
        assert cleaned == clean
        assert stats.total == 0


class TestCheckMarkdown:
    def test_reports_without_mutating(self, tmp_path: Path) -> None:
        doc = _write_doc(tmp_path, "report", _doc("report", "a   \n\n\n\nb\n"))
        before = doc.read_text(encoding="utf-8")

        result = check_markdown(tmp_path)

        assert result.check_name == "markdown"
        assert result.warning_count == 1
        assert result.fixed_count == 0
        assert result.diagnostics[0].fixable is True
        assert doc.read_text(encoding="utf-8") == before

    def test_fix_repairs_and_reports_info(self, tmp_path: Path) -> None:
        doc = _write_doc(tmp_path, "fixme", _doc("fixme", "a   \n\n\n\nb"))

        result = check_markdown(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert result.diagnostics[0].severity.value == "info"
        text = doc.read_text(encoding="utf-8")
        assert "a   \n" not in text
        assert "\n\n\n" not in text
        assert text.endswith("b\n")

    def test_fix_is_idempotent(self, tmp_path: Path) -> None:
        _write_doc(tmp_path, "idem", _doc("idem", "a   \n\n\n\nb"))
        check_markdown(tmp_path, fix=True)
        second = check_markdown(tmp_path, fix=True)
        assert second.fixed_count == 0
        assert second.is_clean

    def test_preserves_crlf_newlines(self, tmp_path: Path) -> None:
        path = tmp_path / ".vault" / "research" / "2026-06-24-crlf-research.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = _doc("crlf", "a   \n\n\n\nb\n").replace("\n", "\r\n")
        path.write_bytes(content.encode("utf-8"))

        check_markdown(tmp_path, fix=True)

        raw = path.read_bytes()
        assert b"\r\n" in raw
        assert b"a   \r\n" not in raw
        # No bare LF was introduced.
        assert raw.replace(b"\r\n", b"").count(b"\n") == 0

    def test_clean_document_is_clean(self, tmp_path: Path) -> None:
        _write_doc(tmp_path, "clean", _doc("clean", "a\n\nb\n"))
        result = check_markdown(tmp_path)
        assert result.is_clean

    def test_feature_filter(self, tmp_path: Path) -> None:
        _write_doc(tmp_path, "alpha", _doc("alpha", "a   \nb\n"))
        _write_doc(tmp_path, "beta", _doc("beta", "c   \nd\n"))
        result = check_markdown(tmp_path, feature="alpha")
        assert result.warning_count == 1
        assert "alpha" in str(result.diagnostics[0].path)
