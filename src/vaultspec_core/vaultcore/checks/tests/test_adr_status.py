"""Tests for the adr-status canonical-taxonomy checker."""

import pytest

from ....core.enums import AdrStatus
from ...models import DocumentMetadata
from .._base import Severity
from ..adr_status import check_adr_status

pytestmark = [pytest.mark.unit]


def _adr_body(status_line: str) -> str:
    """Return an ADR body whose H1 carries *status_line* verbatim."""
    return f"{status_line}\n\n## Problem Statement\n\nBody.\n"


def _snapshot(root, name, body, *, tags=None, superseded_by=None):
    """Build a one-document snapshot for an ADR under ``.vault/adr/``."""
    path = root / ".vault" / "adr" / f"{name}.md"
    meta = DocumentMetadata(
        tags=tags if tags is not None else ["#adr", "#demo"],
        superseded_by=superseded_by,
    )
    return path, {path: (meta, body)}


class TestCanonicalStatus:
    def test_canonical_quoted_status_is_clean(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title` | (**status:** `accepted`)"),
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert result.is_clean

    def test_every_canonical_value_is_clean(self, tmp_path):
        for value in (s.value for s in AdrStatus):
            _, snap = _snapshot(
                tmp_path,
                f"2026-01-01-{value}-adr",
                _adr_body(f"# `demo` adr: `Title` | (**status:** `{value}`)"),
                superseded_by="2026-02-02-next-adr"
                if value == AdrStatus.SUPERSEDED.value
                else None,
            )
            result = check_adr_status(tmp_path, snapshot=snap)
            assert result.is_clean, f"{value} should validate clean"


class TestDivergences:
    def test_off_taxonomy_token_warns(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title` | (**status:** `approved`)"),
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert not result.is_clean
        assert result.diagnostics[0].severity is Severity.WARNING
        assert "outside the canonical set" in result.diagnostics[0].message

    def test_missing_status_warns(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title`"),
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert any("no parseable status" in d.message for d in result.diagnostics)

    def test_legacy_status_section_warns(self, tmp_path):
        body = "# ADR: Demo\n\n## Status\n\nAccepted\n\n## Context\n\nText.\n"
        _, snap = _snapshot(tmp_path, "2026-01-01-demo-adr", body)
        result = check_adr_status(tmp_path, snapshot=snap)
        assert any(
            "legacy '## Status' section" in d.message for d in result.diagnostics
        )

    def test_unpropagated_supersession_warns(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title` | (**status:** `accepted`)"),
            superseded_by="2026-02-02-next-adr",
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert any(
            "superseded_by" in d.message and "not 'superseded'" in d.message
            for d in result.diagnostics
        )

    def test_superseded_with_frontmatter_is_clean(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title` | (**status:** `superseded`)"),
            superseded_by="2026-02-02-next-adr",
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert result.is_clean


class TestQuotingFix:
    def test_bare_token_warns_fixable(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-demo-adr",
            _adr_body("# `demo` adr: `Title` | (**status:** accepted)"),
        )
        result = check_adr_status(tmp_path, snapshot=snap)
        assert not result.is_clean
        diag = result.diagnostics[0]
        assert diag.severity is Severity.WARNING
        assert diag.fixable is True

    def test_fix_quotes_bare_token_on_disk(self, tmp_path):
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True)
        path = adr_dir / "2026-01-01-demo-adr.md"
        body = _adr_body("# `demo` adr: `Title` | (**status:** accepted)")
        path.write_text(
            "---\ntags:\n  - '#adr'\n  - '#demo'\n---\n\n" + body,
            encoding="utf-8",
        )
        meta = DocumentMetadata(tags=["#adr", "#demo"])
        snapshot = {path: (meta, body)}

        result = check_adr_status(tmp_path, snapshot=snapshot, fix=True)

        assert result.fixed_count == 1
        content = path.read_text(encoding="utf-8")
        assert "(**status:** `accepted`)" in content


class TestScoping:
    def test_non_adr_paths_ignored(self, tmp_path):
        path = tmp_path / ".vault" / "plan" / "2026-01-01-demo-plan.md"
        meta = DocumentMetadata(tags=["#plan", "#demo"])
        body = _adr_body("# `demo` plan")
        result = check_adr_status(tmp_path, snapshot={path: (meta, body)})
        assert result.is_clean

    def test_feature_filter_excludes_other_features(self, tmp_path):
        _, snap = _snapshot(
            tmp_path,
            "2026-01-01-other-adr",
            _adr_body("# `other` adr: `Title` | (**status:** `approved`)"),
            tags=["#adr", "#other"],
        )
        result = check_adr_status(tmp_path, snapshot=snap, feature="demo")
        assert result.is_clean
