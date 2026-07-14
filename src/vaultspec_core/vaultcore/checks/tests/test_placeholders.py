"""Tests for the template placeholder checker."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .._base import Severity, VaultSnapshot
from ..placeholders import (
    KNOWN_PLACEHOLDERS,
    check_placeholders,
    is_template_placeholder,
)

if TYPE_CHECKING:
    from pathlib import Path

from ...models import DocumentMetadata

pytestmark = [pytest.mark.unit]

_ROOT_STR = "/fake/root"


def _snap(name: str, body: str) -> tuple[Path, VaultSnapshot]:
    """Build a single-document snapshot for testing."""
    from pathlib import Path

    root = Path(_ROOT_STR)
    doc_path = root / ".vault" / "adr" / f"{name}.md"
    metadata = DocumentMetadata(
        tags=["#adr", "#test-feature"],
        date="2026-06-24",
    )
    return root, {doc_path: (metadata, body)}


class TestCheckPlaceholders:
    def test_reports_error_for_bare_known_placeholder(self):
        root, snapshot = _snap("doc1", "Replace {feature} with the real value.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert result.diagnostics[0].severity == Severity.ERROR
        assert "{feature}" in result.diagnostics[0].message

    def test_enum_placeholder_reported_as_choice(self):
        root, snapshot = _snap("doc2", "Status is {proposed|accepted|rejected}.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        msg = result.diagnostics[0].message
        assert "enum" in msg
        assert "proposed, accepted, rejected" in msg

    def test_placeholder_in_heading_backticks_is_flagged(self):
        root, snapshot = _snap("doc3", "# `{feature}` plan\n\nBody.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert "{feature}" in result.diagnostics[0].message

    def test_placeholder_in_inline_code_non_heading_is_ignored(self):
        root, snapshot = _snap(
            "doc4", 'The f-string `f"x.{feature}"` documents a field.'
        )
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_placeholder_in_double_backtick_span_is_ignored(self):
        root, snapshot = _snap("doc5", "Write the heading as ``# `{feature}` plan``.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_placeholder_in_prose_survives_sibling_inline_code_span(self):
        # An inline code span earlier on the same line must not shield a real
        # placeholder appearing later in prose on that line.
        body = "Run `vaultspec-core sync` then replace {feature} with the tag."
        root, snapshot = _snap("doc5b", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert "{feature}" in result.diagnostics[0].message

    def test_placeholder_in_fenced_code_block_is_ignored(self):
        body = "Text.\n\n```python\nschema = f'x.{feature}.y'\n```\n\nMore."
        root, snapshot = _snap("doc6", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_placeholder_in_tilde_fenced_block_is_ignored(self):
        body = "Text.\n\n~~~\nschema = f'x.{feature}.y'\n~~~\n\nMore."
        root, snapshot = _snap("doc6b", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_unclosed_fence_consumes_rest_of_document(self):
        # CommonMark: a fence with no matching close runs to end of document -
        # the tail is not prose just because the author forgot to close it.
        body = "Text.\n\n```python\nschema = f'x.{feature}.y'\n"
        root, snapshot = _snap("doc6c", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_longer_fence_can_contain_shorter_fence_markers(self):
        # A four-backtick fence's content may itself contain a literal triple-
        # backtick run without closing the block early.
        body = "Text.\n\n````\nsome ``` triple backticks with {feature}\n````\n\nMore."
        root, snapshot = _snap("doc6d", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_closing_fence_shorter_than_opening_does_not_close(self):
        # A three-backtick line cannot close a four-backtick fence; the block
        # keeps running (to the real close, or to EOF) per CommonMark.
        body = (
            "Text.\n\n````\ncode {feature}\n```\nstill code {topic}\n````\n\n"
            "More clean."
        )
        root, snapshot = _snap("doc6e", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_prose_placeholder_after_a_closed_fence_is_still_flagged(self):
        body = "```python\nx = f'{feature}'\n```\n\nReplace {topic} for real."
        root, snapshot = _snap("doc6f", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert "{topic}" in result.diagnostics[0].message

    def test_placeholder_in_html_comment_is_ignored(self):
        body = "<!-- Replace {feature} with a kebab-case tag. -->\n\nClean prose."
        root, snapshot = _snap("doc7", body)
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_unknown_brace_token_is_ignored(self):
        root, snapshot = _snap("doc8", "Writes to {target_dir} and prints {exc}.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_shell_expansion_is_ignored(self):
        root, snapshot = _snap("doc9", "Run with ${feature} exported.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_double_brace_escape_is_ignored(self):
        root, snapshot = _snap("doc10", "Template renders {{feature}} literally.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_json_literal_is_ignored(self):
        root, snapshot = _snap("doc11", 'Payload { "feature": 1 } stays.')
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_regex_quantifier_is_ignored(self):
        root, snapshot = _snap("doc12", r"The pattern \d{4}-\d{2} matches dates.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_date_placeholder_is_flagged(self):
        root, snapshot = _snap("doc13", "Created on {yyyy-mm-dd} today.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert "{yyyy-mm-dd}" in result.diagnostics[0].message

    def test_machine_filled_placeholder_is_flagged(self):
        root, snapshot = _snap("doc14", "Index body:\n\n{document_list}\n")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 1
        assert "{document_list}" in result.diagnostics[0].message

    def test_multiple_placeholders_in_one_document(self):
        root, snapshot = _snap("doc15", "{feature} and {topic} and {title}.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.error_count == 3

    def test_clean_document_returns_clean_result(self):
        root, snapshot = _snap("doc16", "Fully authored prose, nothing remaining.")
        result = check_placeholders(root, snapshot=snapshot)
        assert result.is_clean

    def test_does_not_support_fix(self):
        root, snapshot = _snap("doc17", "Body.")
        result = check_placeholders(root, snapshot=snapshot)
        assert not result.supports_fix
        assert result.check_name == "placeholders"

    def test_feature_filter(self):
        from pathlib import Path

        root = Path(_ROOT_STR)
        path_a = root / ".vault" / "adr" / "a.md"
        path_b = root / ".vault" / "adr" / "b.md"
        meta_a = DocumentMetadata(tags=["#adr", "#alpha"], date="2026-06-24")
        meta_b = DocumentMetadata(tags=["#adr", "#beta"], date="2026-06-24")
        snapshot: VaultSnapshot = {
            path_a: (meta_a, "Has {feature} placeholder."),
            path_b: (meta_b, "Has {topic} placeholder."),
        }
        result = check_placeholders(root, snapshot=snapshot, feature="alpha")
        assert result.error_count == 1
        assert "{feature}" in result.diagnostics[0].message


class TestIsTemplatePlaceholder:
    def test_known_name(self):
        assert is_template_placeholder("{feature}")

    def test_enum(self):
        assert is_template_placeholder("{a|b|c}")

    def test_date_form(self):
        assert is_template_placeholder("{yyyy-mm-dd-*-plan}")

    def test_unknown_name(self):
        assert not is_template_placeholder("{provider}")

    def test_known_set_is_non_empty(self):
        assert "feature" in KNOWN_PLACEHOLDERS


def test_allowlist_covers_all_builtin_template_placeholders():
    """Every placeholder the shipped templates seed must be recognised.

    Guards against drift: if a template adds a new placeholder, the allowlist
    (or the date / enum rules) must learn it, or this check would silently
    miss that residue in authored documents.
    """
    from pathlib import Path

    import vaultspec_core

    from ..placeholders import _PLACEHOLDER_RE

    templates_dir = Path(vaultspec_core.__file__).parent / "builtins" / "templates"
    tokens: set[str] = set()
    for template in templates_dir.glob("*.md"):
        text = template.read_text(encoding="utf-8")
        tokens.update(match.group(0) for match in _PLACEHOLDER_RE.finditer(text))

    assert tokens, "expected to find placeholder tokens in builtin templates"
    unknown = {t for t in tokens if not is_template_placeholder(t)}
    assert not unknown, (
        f"template placeholders missing from allowlist: {sorted(unknown)}"
    )
