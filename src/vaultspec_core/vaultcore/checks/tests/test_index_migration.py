"""Tests for the legacy root-level index detection in ``check_structure``.

After the migration registry took over the mutation, ``check_structure``
warns about misplaced ``<feature>.index.md`` files but never relocates
them. The relocation is exercised in
``src/vaultspec_core/migrations/tests/test_index_subfolder.py``.

These tests use real filesystem fixtures (no mocks) and assert the
detection-only behaviour against the on-disk tree before any migration
runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from .._base import Severity
from ..structure import _ensure_index_directory_tag, check_structure

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


@pytest.fixture(autouse=True)
def _reset_migration_cache():
    """Clear the per-process registry cache so each test starts clean.

    ``scan_vault`` short-circuits the migration check after the first
    successful read for a given workspace path. Without this reset the
    second test reusing the same workspace path would observe stale
    state.
    """
    from ....migrations import reset_workspace_cache

    reset_workspace_cache()
    yield
    reset_workspace_cache()


def _write_legacy_index(
    vault_root: Path,
    feature: str,
    *,
    include_index_tag: bool = False,
    related: list[str] | None = None,
) -> Path:
    """Plant a legacy root-level index file in *vault_root*.

    Args:
        vault_root: Project root containing the ``.vault/`` directory.
        feature: Feature name (without ``#`` prefix).
        include_index_tag: When ``True``, the planted file already
            carries ``#index`` in its tags block.
        related: Optional list of bare wiki-link stems for the
            ``related:`` field.

    Returns:
        Path to the newly written legacy index file.
    """
    docs = vault_root / ".vault"
    docs.mkdir(parents=True, exist_ok=True)
    related_lines = "related: []"
    if related:
        related_lines = "related:\n" + "\n".join(
            f"  - '[[{stem}]]'" for stem in related
        )

    tag_lines = ["  - '#index'"] if include_index_tag else []
    tag_lines.append(f"  - '#{feature}'")
    tag_block = "\n".join(tag_lines)

    content = (
        "---\n"
        "generated: true\n"
        "tags:\n"
        f"{tag_block}\n"
        "date: '2026-04-30'\n"
        f"{related_lines}\n"
        "---\n\n"
        f"# `{feature}` feature index\n\n"
        f"Auto-generated index of all documents tagged with `#{feature}`.\n"
    )
    path = docs / f"{feature}.index.md"
    path.write_text(content, encoding="utf-8")
    return path


def _vault_with_minimal_skeleton(vault_root: Path) -> None:
    """Create the minimum subdirectory layout the structure checker expects."""
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (vault_root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


class TestEnsureIndexDirectoryTag:
    def test_inserts_index_tag_into_tags_block(self):
        before = (
            "---\n"
            "generated: true\n"
            "tags:\n"
            "  - '#my-feat'\n"
            "date: '2026-04-30'\n"
            "related: []\n"
            "---\n\n"
            "# body\n"
        )
        after, changed = _ensure_index_directory_tag(before)
        assert changed is True
        assert "  - '#index'" in after
        assert "  - '#my-feat'" in after
        # The inserted tag must appear inside the YAML frontmatter,
        # before the closing fence.
        closing_fence_idx = after.index("\n---\n", after.index("---\n") + 4)
        assert after.index("'#index'") < closing_fence_idx

    def test_idempotent_when_index_tag_present(self):
        content = (
            "---\n"
            "generated: true\n"
            "tags:\n"
            "  - '#index'\n"
            "  - '#my-feat'\n"
            "date: '2026-04-30'\n"
            "related: []\n"
            "---\n"
        )
        after, changed = _ensure_index_directory_tag(content)
        assert changed is False
        assert after == content

    def test_preserves_crlf_newline_convention(self):
        before = (
            "---\r\n"
            "generated: true\r\n"
            "tags:\r\n"
            "  - '#my-feat'\r\n"
            "date: '2026-04-30'\r\n"
            "related: []\r\n"
            "---\r\n\r\n"
            "# body\r\n"
        )
        after, changed = _ensure_index_directory_tag(before)
        assert changed is True
        # The inserted line must end with CRLF, not LF, so the file does
        # not get mixed line endings.
        assert "\r\n  - '#index'\r\n" in after
        # No bare LF must appear outside of CRLF pairs.
        # (Strip CRLFs first; what remains should have no leftover \n.)
        without_crlf = after.replace("\r\n", "")
        assert "\n" not in without_crlf

    def test_does_not_treat_index_substring_as_already_present(self):
        # A tag like ``#index-notes`` contains the literal string
        # ``#index`` but is a different tag. A naive substring check
        # would set ``has_index_tag = True`` and skip the mandatory
        # insertion. The tag detection must compare the captured
        # value exactly.
        before = (
            "---\n"
            "generated: true\n"
            "tags:\n"
            "  - '#index-notes'\n"
            "  - '#my-feat'\n"
            "date: '2026-04-30'\n"
            "related: []\n"
            "---\n\n"
            "# body\n"
        )
        after, changed = _ensure_index_directory_tag(before)
        assert changed is True, (
            "#index-notes is a different tag; #index must still be inserted"
        )
        assert "  - '#index'\n" in after
        assert "  - '#index-notes'\n" in after

    def test_preserves_lf_newline_convention(self):
        before = (
            "---\n"
            "generated: true\n"
            "tags:\n"
            "  - '#my-feat'\n"
            "date: '2026-04-30'\n"
            "related: []\n"
            "---\n"
        )
        after, changed = _ensure_index_directory_tag(before)
        assert changed is True
        # No CRLF pair should appear in an originally-LF file.
        assert "\r\n" not in after
        assert "\n  - '#index'\n" in after


class TestCheckStructureWarnsLegacyIndex:
    """Detection-only branch: the checker must not mutate the workspace."""

    def test_warns_on_legacy_root_index(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        legacy = _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        legacy_diags = [
            d
            for d in result.diagnostics
            if d.path is not None and d.path.name == legacy.name
        ]
        assert any(d.severity == Severity.WARNING for d in legacy_diags), (
            "structure check must surface a pending-migration warning"
        )
        assert all(not d.fixable for d in legacy_diags), (
            "the warning must not advertise itself as --fix-able; "
            "migration moved to the registry"
        )
        assert legacy.exists(), "structure check must never mutate"

    def test_warns_in_fix_mode_too(self, tmp_path):
        # --fix is for ongoing-hygiene fixes only. Legacy indexes
        # always surface as warnings; mutation is the registry's job.
        _vault_with_minimal_skeleton(tmp_path)
        legacy = _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        legacy_diags = [
            d
            for d in result.diagnostics
            if d.path is not None and d.path.name == legacy.name
        ]
        assert any(d.severity == Severity.WARNING for d in legacy_diags)
        assert legacy.exists(), (
            "--fix must not relocate the legacy file; migration moved to the registry"
        )

    def test_canonical_index_under_subfolder_is_not_flagged(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        canonical_dir = tmp_path / ".vault" / "index"
        canonical_dir.mkdir(parents=True, exist_ok=True)
        canonical = canonical_dir / "alpha.index.md"
        canonical.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha\n",
            encoding="utf-8",
        )

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        legacy_diags = [
            d
            for d in result.diagnostics
            if "Legacy feature index" in d.message
            or "Pending schema migration" in d.message
        ]
        assert legacy_diags == [], (
            "canonical subfolder index must not trigger pending-migration diagnostics"
        )

    def test_no_duplicate_diagnostic(self, tmp_path):
        # A root-level legacy index must surface exactly one
        # actionable per-file warning. The aggregate
        # validate_vault_structure ``Legacy feature index`` message
        # is suppressed in favour of the per-file detection.
        _vault_with_minimal_skeleton(tmp_path)
        _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        legacy_diags = [
            d
            for d in result.diagnostics
            if "Legacy feature index" in d.message
            or "Misplaced feature index" in d.message
            or "Pending schema migration" in d.message
        ]
        assert len(legacy_diags) == 1, (
            f"expected exactly one legacy/misplaced diagnostic per offence, "
            f"got {len(legacy_diags)}: {[d.message for d in legacy_diags]}"
        )
        assert legacy_diags[0].path is not None, (
            "the surviving diagnostic must be the actionable per-file message, "
            "not the pathless aggregate"
        )

    def test_warns_on_misplaced_index_in_typed_subdir(self, tmp_path):
        # An index file misplaced into a typed subdirectory (e.g.
        # ``adr/<feature>.index.md``) was previously a blind spot
        # before #91. The detection must flag it as a pending
        # migration regardless of which subdir it lives in.
        _vault_with_minimal_skeleton(tmp_path)
        misplaced = tmp_path / ".vault" / "adr" / "beta.index.md"
        misplaced.write_text(
            "---\ngenerated: true\ntags:\n  - '#beta'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# beta\n",
            encoding="utf-8",
        )

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        misplaced_diags = [
            d
            for d in result.diagnostics
            if d.path is not None and d.path.name == misplaced.name
        ]
        assert any(d.severity == Severity.WARNING for d in misplaced_diags)
        assert misplaced.exists()
