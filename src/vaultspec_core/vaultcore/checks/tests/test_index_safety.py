"""Tests verifying all checkers handle generated index files correctly.

Post-#91 index files (``<feature>.index.md``) carry the standard
two-tag shape (``#index`` directory tag plus the feature tag) and the
``generated: true`` content marker. Frontmatter validation runs on
them like every other document. Other checkers continue to special-
case indexes for semantic reasons that have nothing to do with
frontmatter shape:

- ``body-links`` skips them because their body legitimately contains
  wiki-links to feature docs (the auto-generated inventory).
- ``orphans`` skips them because indexes have only outgoing links by
  design.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .._base import Severity, is_generated_index

if TYPE_CHECKING:
    from .._base import VaultSnapshot

from ...models import DocumentMetadata

pytestmark = [pytest.mark.unit]

_ROOT = Path("/fake/root")


def _index_snapshot(
    feature: str = "my-feat",
    *,
    legacy: bool = False,
) -> VaultSnapshot:
    """Build a snapshot containing one generated index file.

    Args:
        feature: Feature name (without ``#`` prefix).
        legacy: When ``True``, place the index at the docs root (legacy
            location). Otherwise place it under ``index/`` (canonical).
    """
    if legacy:
        doc_path = _ROOT / ".vault" / f"{feature}.index.md"
        tags = [f"#{feature}"]
    else:
        doc_path = _ROOT / ".vault" / "index" / f"{feature}.index.md"
        tags = ["#index", f"#{feature}"]
    metadata = DocumentMetadata(
        tags=tags,
        date="2026-03-23",
        related=["[[doc-a]]", "[[doc-b]]"],
    )
    body = (
        f"# `{feature}` feature index\n\n"
        "Auto-generated index.\n\n"
        "## Documents\n\n"
        "- [[doc-a]] - Doc A\n"
        "- [[doc-b]] - Doc B\n"
    )
    return {doc_path: (metadata, body)}


def _normal_snapshot() -> VaultSnapshot:
    """Build a snapshot with a normal document (not index)."""
    doc_path = _ROOT / ".vault" / "adr" / "2026-03-01-feat-adr.md"
    metadata = DocumentMetadata(
        tags=["#adr", "#my-feat"],
        date="2026-03-23",
        related=[],
    )
    return {doc_path: (metadata, "Clean body.")}


class TestIsGeneratedIndex:
    def test_detects_index_file(self):
        assert is_generated_index(Path("my-feat.index.md"))

    def test_rejects_normal_file(self):
        assert not is_generated_index(Path("2026-03-01-feat-adr.md"))

    def test_detects_with_full_path(self):
        p = Path("/project/.vault/my-feat.index.md")
        assert is_generated_index(p)

    def test_detects_under_index_subfolder(self):
        p = Path("/project/.vault/index/my-feat.index.md")
        assert is_generated_index(p)


class TestFrontmatterIndexValidation:
    """Indexes carry the standard two-tag shape post-#91 and run
    through frontmatter validation like every other document.
    """

    def test_canonical_index_frontmatter_passes(self):
        # A canonical post-migration index has two tags
        # (#index + #feature), valid date, and well-formed related
        # entries; the frontmatter checker must report it clean.
        from ..frontmatter import check_frontmatter

        snapshot = _index_snapshot()
        result = check_frontmatter(_ROOT, snapshot=snapshot)
        assert result.is_clean

    def test_legacy_root_index_frontmatter_flagged(self):
        # An unmigrated legacy root-level index carries only one tag
        # (the feature tag, missing #index). The exemption used to
        # silence this; per ADR alignment indexes are no longer
        # exempt and the missing directory tag must surface.
        from ..frontmatter import check_frontmatter

        snapshot = _index_snapshot(legacy=True)
        result = check_frontmatter(_ROOT, snapshot=snapshot)
        assert not result.is_clean
        # The actionable diagnostic is the "exactly one directory tag"
        # message - the legacy file has zero, not one.
        assert any("directory tag" in d.message.lower() for d in result.diagnostics)

    def test_normal_doc_still_checked(self):
        from ..frontmatter import check_frontmatter

        # A doc with only 1 tag should fail
        doc_path = _ROOT / ".vault" / "adr" / "bad.md"
        metadata = DocumentMetadata(tags=["#adr"], date="2026-03-23", related=[])
        snapshot: VaultSnapshot = {
            doc_path: (metadata, "Body."),
        }
        result = check_frontmatter(_ROOT, snapshot=snapshot)
        assert not result.is_clean


class TestStructureSkipsIndex:
    def test_index_file_not_flagged_by_filename_check(self):
        from ..structure import check_structure

        snapshot = _index_snapshot()
        result = check_structure(_ROOT, snapshot=snapshot)
        # Only check filename-level diagnostics (not directory-level
        # which depend on actual filesystem)
        filename_diags = [d for d in result.diagnostics if d.path is not None]
        assert len(filename_diags) == 0


class TestOrphansSkipsIndex:
    def test_index_file_not_flagged_as_orphan(self):
        """Index files should be skipped even if they appear orphaned."""
        # Verify the predicate that drives the orphans checker's skip
        # logic; full graph integration is covered elsewhere.
        p = _ROOT / ".vault" / "my-feat.index.md"
        assert is_generated_index(p)


class TestBodyLinksSkipsIndex:
    def test_index_file_wiki_links_not_flagged(self):
        from ..body_links import check_body_links

        snapshot = _index_snapshot()
        result = check_body_links(_ROOT, snapshot=snapshot)
        assert result.is_clean

    def test_legacy_root_index_wiki_links_not_flagged(self):
        from ..body_links import check_body_links

        snapshot = _index_snapshot(legacy=True)
        result = check_body_links(_ROOT, snapshot=snapshot)
        assert result.is_clean


class TestFeaturesDetectsMissingIndex:
    def test_warns_when_no_index_exists(self):
        from ..features import check_features

        # Normal docs but no index file
        snapshot = _normal_snapshot()
        result = check_features(_ROOT, snapshot=snapshot)
        missing_diags = [
            d for d in result.diagnostics if "no feature index" in d.message
        ]
        assert len(missing_diags) == 1
        assert "my-feat" in missing_diags[0].message
        assert missing_diags[0].severity == Severity.WARNING

    def test_no_warning_when_index_exists(self):
        from ..features import check_features

        # Merge normal docs + index
        snapshot: VaultSnapshot = {
            **_normal_snapshot(),
            **_index_snapshot(),
        }
        result = check_features(_ROOT, snapshot=snapshot)
        missing_diags = [
            d for d in result.diagnostics if "no feature index" in d.message
        ]
        assert len(missing_diags) == 0

    def test_no_warning_when_legacy_root_index_exists(self):
        from ..features import check_features

        snapshot: VaultSnapshot = {
            **_normal_snapshot(),
            **_index_snapshot(legacy=True),
        }
        result = check_features(_ROOT, snapshot=snapshot)
        missing_diags = [
            d for d in result.diagnostics if "no feature index" in d.message
        ]
        assert len(missing_diags) == 0


class TestFeaturesDetectsStaleIndex:
    def test_warns_when_index_related_count_mismatches(self):
        from ..features import check_features

        # Index has 2 related links but feature has 3 docs
        index_path = _ROOT / ".vault" / "my-feat.index.md"
        index_meta = DocumentMetadata(
            tags=["#my-feat"],
            date="2026-03-23",
            related=["[[doc-a]]", "[[doc-b]]"],
        )
        doc_paths = [
            _ROOT / ".vault" / "adr" / "a.md",
            _ROOT / ".vault" / "adr" / "b.md",
            _ROOT / ".vault" / "plan" / "c.md",
        ]
        snapshot: VaultSnapshot = {
            index_path: (index_meta, "Index body."),
        }
        for p in doc_paths:
            snapshot[p] = (
                DocumentMetadata(
                    tags=["#adr", "#my-feat"],
                    date="2026-03-23",
                    related=[],
                ),
                "Body.",
            )

        result = check_features(_ROOT, snapshot=snapshot)
        stale_diags = [d for d in result.diagnostics if "stale" in d.message]
        assert len(stale_diags) == 1
        assert "2 links" in stale_diags[0].message
        assert "3 documents" in stale_diags[0].message

    def test_no_warning_when_counts_match(self):
        from ..features import check_features

        # Index has 1 related link and feature has 1 doc
        index_path = _ROOT / ".vault" / "my-feat.index.md"
        index_meta = DocumentMetadata(
            tags=["#my-feat"],
            date="2026-03-23",
            related=["[[doc-a]]"],
        )
        doc_path = _ROOT / ".vault" / "adr" / "a.md"
        doc_meta = DocumentMetadata(
            tags=["#adr", "#my-feat"],
            date="2026-03-23",
            related=[],
        )
        snapshot: VaultSnapshot = {
            index_path: (index_meta, "Index body."),
            doc_path: (doc_meta, "Body."),
        }
        result = check_features(_ROOT, snapshot=snapshot)
        stale_diags = [d for d in result.diagnostics if "stale" in d.message]
        assert len(stale_diags) == 0
