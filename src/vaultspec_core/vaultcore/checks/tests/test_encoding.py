"""Real-filesystem tests for the ``encoding`` checker and BOM discovery.

Exercises two behaviours against real on-disk vaults built with real bytes,
with no test doubles:

- The BOM discovery fix: a UTF-8-BOM authored document is now discovered by
  ``list_documents`` and renamed by ``rename_feature`` with its leading BOM
  preserved byte-for-byte.
- The ``encoding`` checker: a UTF-16 or Latin-1 ``.md`` is surfaced as an
  ERROR, while plain UTF-8 and UTF-8-BOM files pass; ``_archive`` and
  ``.obsidian`` subtrees and symlinks are skipped; and ``vault check all``
  surfaces the encoding errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ...query import list_documents, rename_feature
from .._base import Severity
from ..encoding import check_encoding

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

DATE = "2026-06-26"
BOM = b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# Document builders (real bytes, schema-valid frontmatter).
# ---------------------------------------------------------------------------


def _frontmatter(doc_type: str, feature: str) -> str:
    return (
        f"---\ntags:\n  - '#{doc_type}'\n  - '#{feature}'\n"
        f"date: '{DATE}'\nmodified: '{DATE}'\nrelated: []\n---\n"
    )


def _write_bom_doc(root: Path, doc_type: str, feature: str) -> Path:
    """Write a UTF-8-BOM authored document and return its path."""
    fm = _frontmatter(doc_type, feature)
    body = f"# {feature} {doc_type}\n\nBody for {feature}.\n"
    path = root / ".vault" / doc_type / f"{DATE}-{feature}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(BOM + f"{fm}\n{body}".encode())
    return path


def _write_plain_doc(root: Path, doc_type: str, feature: str) -> Path:
    """Write a plain UTF-8 authored document and return its path."""
    fm = _frontmatter(doc_type, feature)
    body = f"# {feature} {doc_type}\n\nBody for {feature}.\n"
    path = root / ".vault" / doc_type / f"{DATE}-{feature}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{fm}\n{body}", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BOM discovery end-to-end: list_documents + rename_feature
# ---------------------------------------------------------------------------


class TestBomDiscoveryAndRename:
    def test_bom_doc_is_discovered_alongside_plain(self, tmp_path: Path):
        _write_bom_doc(tmp_path, "research", "bom-feature")
        _write_plain_doc(tmp_path, "adr", "bom-feature")

        docs = list_documents(tmp_path, feature="bom-feature")
        names = {d.name for d in docs}
        assert names == {
            f"{DATE}-bom-feature-research",
            f"{DATE}-bom-feature-adr",
        }, "the BOM document must be discovered next to the plain document"

    def test_rename_renames_bom_doc_and_preserves_bom(self, tmp_path: Path):
        bom_path = _write_bom_doc(tmp_path, "research", "bom-feature")
        _write_plain_doc(tmp_path, "adr", "bom-feature")
        assert bom_path.read_bytes().startswith(BOM)

        result = rename_feature(tmp_path, "bom-feature", "renamed-feature")
        assert result["status"] == "updated"
        assert result["renamed_count"] == 2

        # The BOM document moved to the renamed filename and the old one is gone.
        new_path = (
            tmp_path / ".vault" / "research" / f"{DATE}-renamed-feature-research.md"
        )
        assert new_path.is_file()
        assert not bom_path.exists()

        # The leading BOM survives byte-for-byte through the tag rewrite.
        renamed_bytes = new_path.read_bytes()
        assert renamed_bytes.startswith(BOM), "rename dropped the leading BOM"
        # Exactly one BOM, at the very start - not duplicated or shifted.
        assert renamed_bytes.count(BOM) == 1

        # The feature tag was rewritten in the BOM document.
        from ...parser import parse_frontmatter

        meta, _ = parse_frontmatter(new_path.read_text(encoding="utf-8"))
        assert "#renamed-feature" in meta.get("tags", [])
        assert "#bom-feature" not in meta.get("tags", [])

        # The old feature now matches zero documents; the new one matches both
        # authored docs (the regenerated feature index also carries the new tag,
        # so it is excluded from this authored-doc count).
        assert list_documents(tmp_path, feature="bom-feature") == []
        renamed_authored = [
            d
            for d in list_documents(tmp_path, feature="renamed-feature")
            if d.doc_type != "index"
        ]
        assert len(renamed_authored) == 2


# ---------------------------------------------------------------------------
# check_encoding
# ---------------------------------------------------------------------------


class TestCheckEncoding:
    def test_clean_vault_of_utf8_and_bom_has_no_errors(self, tmp_path: Path):
        _write_plain_doc(tmp_path, "research", "clean-feature")
        _write_bom_doc(tmp_path, "adr", "clean-feature")

        result = check_encoding(tmp_path)
        assert result.check_name == "encoding"
        assert result.error_count == 0
        assert result.is_clean

    def test_utf16_and_latin1_reported_as_errors(self, tmp_path: Path):
        _write_plain_doc(tmp_path, "research", "clean-feature")

        utf16_path = tmp_path / ".vault" / "reference" / f"{DATE}-utf16-reference.md"
        utf16_path.parent.mkdir(parents=True, exist_ok=True)
        utf16_path.write_bytes("# UTF-16 doc\n\nBody.\n".encode("utf-16"))

        latin1_path = tmp_path / ".vault" / "reference" / f"{DATE}-latin1-reference.md"
        latin1_path.write_bytes("# Café\n\nPrix du café.\n".encode("latin-1"))

        result = check_encoding(tmp_path)
        assert result.error_count == 2
        flagged = {
            diag.path.name
            for diag in result.diagnostics
            if diag.severity == Severity.ERROR and diag.path is not None
        }
        assert flagged == {utf16_path.name, latin1_path.name}
        for diag in result.diagnostics:
            if diag.severity == Severity.ERROR:
                assert "not valid UTF-8" in diag.message

    def test_archive_and_obsidian_non_utf8_are_skipped(self, tmp_path: Path):
        _write_plain_doc(tmp_path, "research", "clean-feature")

        archived = tmp_path / ".vault" / "_archive" / f"{DATE}-old-research.md"
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes("archived café\n".encode("latin-1"))

        obsidian = tmp_path / ".vault" / ".obsidian" / "notes.md"
        obsidian.parent.mkdir(parents=True, exist_ok=True)
        obsidian.write_bytes("obsidian café\n".encode("latin-1"))

        result = check_encoding(tmp_path)
        assert result.error_count == 0, (
            "non-UTF-8 files under _archive/.obsidian must be skipped"
        )

    def test_encoding_runs_vault_wide(self, tmp_path: Path):
        # Encoding is validated vault-wide (no feature filter): a non-UTF-8 doc
        # has no parseable feature tag, so it is flagged wherever it lives.
        latin1_path = tmp_path / ".vault" / "reference" / f"{DATE}-latin1-reference.md"
        latin1_path.parent.mkdir(parents=True, exist_ok=True)
        latin1_path.write_bytes("# Café\n\nProse.\n".encode("latin-1"))

        result = check_encoding(tmp_path)
        assert result.error_count == 1
        flagged = result.diagnostics[0].path
        assert flagged is not None and flagged.name == latin1_path.name

    def test_vault_check_all_surfaces_encoding_errors(self, tmp_path: Path):
        from .. import run_all_checks

        _write_plain_doc(tmp_path, "research", "clean-feature")
        latin1_path = tmp_path / ".vault" / "reference" / f"{DATE}-latin1-reference.md"
        latin1_path.parent.mkdir(parents=True, exist_ok=True)
        latin1_path.write_bytes("# Café\n\nProse.\n".encode("latin-1"))

        results = run_all_checks(tmp_path, fix=False)
        by_name = {r.check_name: r for r in results}
        assert "encoding" in by_name, "run_all_checks must include the encoding check"
        assert by_name["encoding"].error_count == 1
        flagged = by_name["encoding"].diagnostics[0].path
        assert flagged is not None and flagged.name == latin1_path.name
