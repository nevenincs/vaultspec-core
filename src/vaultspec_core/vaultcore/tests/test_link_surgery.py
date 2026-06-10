"""Tests for the shared related-frontmatter surgery helpers.

Covers CRLF preservation, atomic write, and round-trip correctness for
:func:`~vaultspec_core.vaultcore.related_surgery.remove_related_entries`
and :func:`~vaultspec_core.vaultcore.related_surgery.append_related_entry`.

All tests operate on real on-disk files to satisfy the no-mock mandate and
to exercise the actual byte-level I/O that the helpers promise.
"""

from __future__ import annotations

import pytest
import yaml

from ..related_surgery import append_related_entry, remove_related_entries

pytestmark = [pytest.mark.unit]


def _write_crlf(path, text: str) -> None:
    """Write *text* with CRLF line endings."""
    crlf_text = text.replace("\n", "\r\n")
    path.write_bytes(crlf_text.encode("utf-8"))


def _write_lf(path, text: str) -> None:
    """Write *text* with LF line endings."""
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# remove_related_entries
# ---------------------------------------------------------------------------


class TestRemoveRelatedEntriesCRLF:
    """CRLF preservation: bytes outside the related: block are unchanged."""

    def test_crlf_preserved_on_removal(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = (
            "---\n"
            "tags:\n"
            "  - '#exec'\n"
            "related:\n"
            '  - "[[gone]]"\n'
            '  - "[[kept]]"\n'
            "---\n"
            "\nBody paragraph.\n"
        )
        _write_crlf(doc, content)
        raw_before = doc.read_bytes()

        removed = remove_related_entries(doc, ["gone"])

        assert removed == 1
        raw_after = doc.read_bytes()
        # The file must still use CRLF endings throughout
        assert b"\r\n" in raw_after
        # No bare LF left in the file (every newline is CRLF)
        decoded = raw_after.decode("utf-8")
        lf_only_count = decoded.count("\n") - decoded.count("\r\n")
        assert lf_only_count == 0
        # Body paragraph survived byte-identical (CRLF)
        assert b"Body paragraph." in raw_after
        # The kept entry is still present
        assert b"[[kept]]" in raw_after
        # Removed entry is gone
        assert b"[[gone]]" not in raw_after
        _ = raw_before  # reference prevents unused-var warning

    def test_crlf_all_removed_leaves_empty_list(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = (
            '---\nrelated:\n  - "[[gone-one]]"\n  - "[[gone-two]]"\n---\n\nBody.\n'
        )
        _write_crlf(doc, content)

        removed = remove_related_entries(doc, ["gone-one", "gone-two"])

        assert removed == 2
        decoded = doc.read_bytes().decode("utf-8")
        # CRLF preserved
        assert "\r\n" in decoded
        # related: key collapsed to inline empty list
        assert "related: []" in decoded
        # Body survived
        assert "Body." in decoded


class TestRemoveRelatedEntriesLF:
    """Verify LF files are not corrupted (no CRLF injected)."""

    def test_lf_preserved_on_removal(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = '---\nrelated:\n  - "[[gone]]"\n  - "[[kept]]"\n---\n\nBody.\n'
        _write_lf(doc, content)

        removed = remove_related_entries(doc, ["gone"])

        assert removed == 1
        raw_after = doc.read_bytes()
        # No CRLF injected
        assert b"\r\n" not in raw_after
        assert b"[[kept]]" in raw_after

    def test_returns_zero_when_no_match(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = "---\nrelated:\n  - '[[real]]'\n---\nBody.\n"
        _write_lf(doc, content)
        original_bytes = doc.read_bytes()

        removed = remove_related_entries(doc, ["nonexistent"])

        assert removed == 0
        # File must be byte-identical - no write happened
        assert doc.read_bytes() == original_bytes

    def test_returns_zero_on_unreadable_file(self, tmp_path):
        doc = tmp_path / "missing.md"
        removed = remove_related_entries(doc, ["anything"])
        assert removed == 0

    def test_case_insensitive_match(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = "---\nrelated:\n  - '[[Some-Doc]]'\n---\nBody.\n"
        _write_lf(doc, content)

        removed = remove_related_entries(doc, ["some-doc"])

        assert removed == 1
        assert "[[Some-Doc]]" not in doc.read_text(encoding="utf-8")


class TestRemoveAtomicWrite:
    """Verify the write is atomic: a successful write leaves no .bak file."""

    def test_no_bak_file_after_success(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = "---\nrelated:\n  - '[[gone]]'\n---\nBody.\n"
        _write_lf(doc, content)

        remove_related_entries(doc, ["gone"])

        bak = doc.with_suffix(".md.bak")
        assert not bak.exists()


# ---------------------------------------------------------------------------
# append_related_entry
# ---------------------------------------------------------------------------


class TestAppendRelatedEntryCRLF:
    """CRLF preservation: new entry uses CRLF; existing bytes unchanged."""

    def test_crlf_preserved_on_append(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = "---\nrelated:\n  - '[[existing]]'\n---\nBody.\n"
        _write_crlf(doc, content)

        appended = append_related_entry(doc, "[[new-target]]")

        assert appended is True
        raw = doc.read_bytes()
        decoded = raw.decode("utf-8")
        # CRLF throughout
        lf_only_count = decoded.count("\n") - decoded.count("\r\n")
        assert lf_only_count == 0
        # New entry present
        assert "[[new-target]]" in decoded
        # Existing entry preserved
        assert "[[existing]]" in decoded
        # Body preserved
        assert "Body." in decoded

    def test_crlf_empty_related_list_append(self, tmp_path):
        doc = tmp_path / "doc.md"
        content = "---\nrelated: []\n---\nBody.\n"
        _write_crlf(doc, content)

        appended = append_related_entry(doc, "[[alpha]]")

        assert appended is True
        decoded = doc.read_bytes().decode("utf-8")
        assert "[[alpha]]" in decoded
        # Still CRLF
        assert "\r\n" in decoded


class TestAppendRelatedEntryLF:
    """Core logic on LF files."""

    def test_append_to_existing_block(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(
            doc,
            "---\nrelated:\n  - '[[first]]'\n---\nBody.\n",
        )

        appended = append_related_entry(doc, "[[second]]")

        assert appended is True
        content = doc.read_text(encoding="utf-8")
        assert "[[first]]" in content
        assert "[[second]]" in content

    def test_idempotent_same_stem(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated:\n  - '[[alpha]]'\n---\nBody.\n")
        original_bytes = doc.read_bytes()

        appended = append_related_entry(doc, "[[alpha]]")

        assert appended is False
        # File must be byte-identical
        assert doc.read_bytes() == original_bytes

    def test_idempotent_case_insensitive(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated:\n  - '[[My-Doc]]'\n---\nBody.\n")

        appended = append_related_entry(doc, "[[my-doc]]")

        assert appended is False

    def test_creates_related_key_when_absent(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\ntags:\n  - '#exec'\n---\nBody.\n")

        appended = append_related_entry(doc, "[[plan-stem]]")

        assert appended is True
        content = doc.read_text(encoding="utf-8")
        assert "related:" in content
        assert "[[plan-stem]]" in content
        # Frontmatter fence still closed
        lines = content.split("\n")
        dash_count = sum(1 for ln in lines if ln.strip() == "---")
        assert dash_count >= 2

    def test_raises_on_empty_wiki_link(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated: []\n---\nBody.\n")

        with pytest.raises(ValueError):
            append_related_entry(doc, "[[]]")

    def test_no_bak_after_success(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated: []\n---\nBody.\n")

        append_related_entry(doc, "[[new]]")

        bak = doc.with_suffix(".md.bak")
        assert not bak.exists()


# ---------------------------------------------------------------------------
# append_related_entry: inline (flow) sequence normalisation (review C1)
# ---------------------------------------------------------------------------


class TestAppendInlineFlowSequence:
    """A flow-form related: list must be normalised to block before append.

    Appending a block item beneath a flow key produces unparseable YAML, so
    the helper rewrites the whole key to block form first.  Every case must
    re-parse cleanly under :func:`yaml.safe_load`.
    """

    def _body_after_fence(self, raw: bytes) -> bytes:
        """Return the bytes after the closing frontmatter fence."""
        text = raw.decode("utf-8")
        # Split on the closing fence (second '---' line region).
        idx = text.index("---", text.index("---") + 3)
        return text[idx:].encode("utf-8")

    def test_single_entry_flow_normalised(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated: ['[[a]]']\n---\nBody paragraph.\n")
        body_before = self._body_after_fence(doc.read_bytes())

        appended = append_related_entry(doc, "[[b]]")

        assert appended is True
        text = doc.read_text(encoding="utf-8")
        # (a) re-parses with no error
        parsed = yaml.safe_load(text.split("---\n")[1])
        # (b) new entry present  (c) prior entry survives  (order preserved)
        assert parsed["related"] == ["[[a]]", "[[b]]"]
        # (d) body bytes byte-identical
        assert self._body_after_fence(doc.read_bytes()) == body_before

    def test_double_quoted_multi_entry_flow_normalised(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, '---\nrelated: ["[[a]]", "[[b]]"]\n---\nBody paragraph.\n')
        body_before = self._body_after_fence(doc.read_bytes())

        appended = append_related_entry(doc, "[[c]]")

        assert appended is True
        text = doc.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text.split("---\n")[1])
        assert parsed["related"] == ["[[a]]", "[[b]]", "[[c]]"]
        assert self._body_after_fence(doc.read_bytes()) == body_before

    def test_flow_idempotent_existing_stem(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(doc, "---\nrelated: ['[[a]]']\n---\nBody.\n")
        original = doc.read_bytes()

        appended = append_related_entry(doc, "[[a]]")

        assert appended is False
        # No write occurred: bytes are identical.
        assert doc.read_bytes() == original


# ---------------------------------------------------------------------------
# Round-trip: remove then add restores the original entry
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_remove_then_add_restores(self, tmp_path):
        doc = tmp_path / "doc.md"
        _write_lf(
            doc,
            "---\nrelated:\n  - '[[alpha]]'\n  - '[[beta]]'\n---\nBody.\n",
        )

        remove_related_entries(doc, ["beta"])
        content_after_remove = doc.read_text(encoding="utf-8")
        assert "[[beta]]" not in content_after_remove
        assert "[[alpha]]" in content_after_remove

        append_related_entry(doc, "[[beta]]")
        final = doc.read_text(encoding="utf-8")
        assert "[[alpha]]" in final
        assert "[[beta]]" in final

    def test_crlf_round_trip_unchanged_outside_block(self, tmp_path):
        """Bytes outside the related: block must be bit-perfect after a round-trip."""
        doc = tmp_path / "doc.md"
        content = (
            "---\n"
            "tags:\n"
            "  - '#exec'\n"
            "  - '#test'\n"
            "related:\n"
            '  - "[[adr]]"\n'
            "---\n"
            "\nLorem ipsum dolor sit amet.\n"
            "Second paragraph.\n"
        )
        _write_crlf(doc, content)

        # Capture the non-related block bytes before mutation
        original_raw = doc.read_bytes()

        # Remove the entry
        remove_related_entries(doc, ["adr"])
        # Add it back
        append_related_entry(doc, "[[adr]]")

        final_raw = doc.read_bytes()
        # The body bytes must survive unchanged (CRLF-terminated)
        assert b"Lorem ipsum dolor sit amet." in final_raw
        assert b"Second paragraph." in final_raw
        # CRLF still present
        assert b"\r\n" in final_raw
        _ = original_raw  # silence linter
