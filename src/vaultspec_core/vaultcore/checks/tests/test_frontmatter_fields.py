"""Tests for the five new frontmatter lifecycle fields.

Covers parsing, validation, serialization, and migration (m_0_1_21).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....migrations.m_0_1_21_frontmatter_lifecycle import migrate as migrate_0_1_21
from ... import DocumentMetadata, parse_vault_metadata
from ..frontmatter import check_frontmatter

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from .._base import CheckResult

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _make_skeleton(root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


def _run_fix(doc: Path, root_dir: Path) -> CheckResult:
    """Drive the frontmatter fixer through its public entry point.

    Builds a one-document snapshot from *doc*'s current on-disk content
    and runs :func:`check_frontmatter` with ``fix=True``, mirroring how
    the real ``vault check`` pipeline invokes the (private) fixer.
    """
    content = doc.read_text(encoding="utf-8")
    metadata, body = parse_vault_metadata(content)
    snapshot = {doc: (metadata, body)}
    return check_frontmatter(root_dir, snapshot=snapshot, fix=True)


def test_parse_new_fields_inline_and_bulleted() -> None:
    # Inline list format
    content_inline = """---
tags: ["#adr", "#feat"]
date: "2026-05-17"
supersedes: ["2026-05-01-old-adr", "2026-05-10-other-adr"]
superseded_by: "2026-05-20-newer-adr"
derived_from: ["audit:2026-05-17-cli-simplification", "finding:B9"]
promoted_to: ["rule:vaultspec-archive-discipline"]
archived: "2026-05-22"
---
# Content
"""
    meta, _ = parse_vault_metadata(content_inline)
    assert meta.tags == ["#adr", "#feat"]
    assert meta.date == "2026-05-17"
    assert meta.supersedes == ["2026-05-01-old-adr", "2026-05-10-other-adr"]
    assert meta.superseded_by == "2026-05-20-newer-adr"
    assert meta.derived_from == ["audit:2026-05-17-cli-simplification", "finding:B9"]
    assert meta.promoted_to == ["rule:vaultspec-archive-discipline"]
    assert meta.archived == "2026-05-22"

    # Bulleted list format
    content_bulleted = """---
tags:
  - "#adr"
  - "#feat"
date: 2026-05-17
body_schema: 'body-v1'
supersedes:
  - "2026-05-01-old-adr"
  - "2026-05-10-other-adr"
superseded_by: 2026-05-20-newer-adr
derived_from:
  - "audit:2026-05-17-cli-simplification"
  - "finding:B9"
promoted_to:
  - "rule:vaultspec-archive-discipline"
archived: 2026-05-22
---
# Content
"""
    meta_b, _ = parse_vault_metadata(content_bulleted)
    assert meta_b.tags == ["#adr", "#feat"]
    assert meta_b.date == "2026-05-17"
    assert meta_b.supersedes == ["2026-05-01-old-adr", "2026-05-10-other-adr"]
    assert meta_b.superseded_by == "2026-05-20-newer-adr"
    assert meta_b.derived_from == ["audit:2026-05-17-cli-simplification", "finding:B9"]
    assert meta_b.promoted_to == ["rule:vaultspec-archive-discipline"]
    assert meta_b.archived == "2026-05-22"


def test_validate_archived_format() -> None:
    # Valid archived date format
    meta = DocumentMetadata(
        tags=["#adr", "#feat"],
        date="2026-05-17",
        archived="2026-05-22",
    )
    assert len(meta.validate()) == 0

    # Invalid archived date format
    meta_invalid = DocumentMetadata(
        tags=["#adr", "#feat"],
        date="2026-05-17",
        archived="2026/05/22",
    )
    errors = meta_invalid.validate()
    assert len(errors) == 1
    assert "Invalid archived date format" in errors[0]


def test_fix_frontmatter_preserves_new_fields(tmp_path: Path) -> None:
    _make_skeleton(tmp_path)
    doc = tmp_path / ".vault" / "adr" / "2026-05-17-test-adr.md"
    doc.write_text(
        """---
feature: my-feature
date: 2026-05-17
body_schema: 'body-v1'
supersedes:
  - "2026-05-01-old-adr"
superseded_by: "2026-05-20-newer-adr"
derived_from:
  - "audit:2026-05-17-cli-simplification"
promoted_to:
  - "rule:vaultspec-archive-discipline"
archived: 2026-05-22
---
# Content
""",
        encoding="utf-8",
    )

    # Run fixing
    result = _run_fix(doc, tmp_path)
    assert result.fixed_count == 1
    assert any(
        "constructed tags from feature field" in d.message for d in result.diagnostics
    )

    # Re-read and parse
    new_content = doc.read_text(encoding="utf-8")
    meta, _ = parse_vault_metadata(new_content)
    assert meta.tags == ["#adr", "#my-feature"]
    assert meta.body_schema == "body-v1"
    assert meta.supersedes == ["2026-05-01-old-adr"]
    assert meta.superseded_by == "2026-05-20-newer-adr"
    assert meta.derived_from == ["audit:2026-05-17-cli-simplification"]
    assert meta.promoted_to == ["rule:vaultspec-archive-discipline"]
    assert meta.archived == "2026-05-22"

    # Make sure we didn't duplicate them as unknown keys
    assert new_content.count("supersedes:") == 1
    assert new_content.count("superseded_by:") == 1
    assert new_content.count("derived_from:") == 1
    assert new_content.count("promoted_to:") == 1
    assert new_content.count("archived:") == 1
    assert new_content.count("body_schema:") == 1


def test_fix_frontmatter_preserves_unknown_keys(tmp_path: Path) -> None:
    _make_skeleton(tmp_path)
    doc = tmp_path / ".vault" / "adr" / "2026-05-17-unknown-adr.md"
    doc.write_text(
        """---
tags:
  - adr
  - my-feature
date: 2026-05-17
custom_scalar: kept
custom_list:
  - one
  - two

trailing_unknown: also kept
---
# Content
""",
        encoding="utf-8",
    )

    result = _run_fix(doc, tmp_path)
    assert result.fixed_count == 1
    assert any(
        d.message == "Fixed: normalized tag # prefixes" for d in result.diagnostics
    )

    new_content = doc.read_text(encoding="utf-8")
    assert "custom_scalar: kept" in new_content
    assert "custom_list:" in new_content
    assert "  - one" in new_content
    assert "  - two" in new_content
    assert "trailing_unknown: also kept" in new_content
    assert new_content.count("date:") == 1
    assert new_content.count("tags:") == 1

    meta, _ = parse_vault_metadata(new_content)
    assert meta.tags == ["#adr", "#my-feature"]


def test_fix_frontmatter_noop_when_nothing_to_fix(tmp_path: Path) -> None:
    _make_skeleton(tmp_path)
    doc = tmp_path / ".vault" / "adr" / "2026-05-17-clean-adr.md"
    original = """---
tags:
  - "#adr"
  - "#my-feature"
date: 2026-05-17
---
# Content
"""
    doc.write_text(original, encoding="utf-8")

    result = _run_fix(doc, tmp_path)
    assert result.fixed_count == 0
    assert doc.read_text(encoding="utf-8") == original


def test_fix_frontmatter_normalizes_date_suffix(tmp_path: Path) -> None:
    _make_skeleton(tmp_path)
    doc = tmp_path / ".vault" / "adr" / "2026-05-17-date-adr.md"
    doc.write_text(
        """---
tags:
  - "#adr"
  - "#my-feature"
date: "2026-05-17 10:30"
---
# Content
""",
        encoding="utf-8",
    )

    result = _run_fix(doc, tmp_path)
    assert result.fixed_count == 1
    assert any(d.message == "Fixed: normalized date format" for d in result.diagnostics)

    meta, _ = parse_vault_metadata(doc.read_text(encoding="utf-8"))
    assert meta.date == "2026-05-17"


def test_migration_0_1_21(tmp_path: Path) -> None:
    # Runs the additive migration which should return successfully
    res = migrate_0_1_21(tmp_path)
    assert res.name == "frontmatter_lifecycle"
    assert res.target_version == "0.1.21"
    assert "no-op" in res.summary
