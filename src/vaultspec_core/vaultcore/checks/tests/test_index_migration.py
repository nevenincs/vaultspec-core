"""Tests for the legacy root-level index file migration.

The structure checker detects ``<feature>.index.md`` files at the docs
root and, with ``fix=True``, relocates them into the configured index
subfolder, inserting the ``#index`` directory tag if missing. These
tests use real filesystem fixtures (no mocks) and assert behaviour
against the on-disk tree before and after migration.
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


class TestCheckStructureDetectsLegacyIndex:
    def test_reports_error_without_fix(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        legacy = _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        legacy_diags = [
            d
            for d in result.diagnostics
            if d.path is not None and d.path.name == legacy.name
        ]
        assert any(d.severity == Severity.ERROR for d in legacy_diags), (
            "structure check must flag legacy root-level index as ERROR"
        )
        assert any(d.fixable for d in legacy_diags), (
            "legacy index ERROR must be marked fixable"
        )
        assert legacy.exists(), "non-fix mode must not move the legacy file"

    def test_fix_relocates_to_index_subfolder(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        legacy = _write_legacy_index(tmp_path, "alpha")
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        assert not legacy.exists(), "fix must remove the legacy root-level file"
        assert target.exists(), "fix must place the file in <docs_dir>/<index_dir>/"
        assert result.fixed_count >= 1

    def test_fix_inserts_index_directory_tag(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        _write_legacy_index(tmp_path, "alpha", include_index_tag=False)
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        graph = VaultGraph(tmp_path)
        check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        text = target.read_text(encoding="utf-8")
        assert "'#index'" in text
        assert "'#alpha'" in text

    def test_fix_idempotent(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)
        target = tmp_path / ".vault" / "index" / "alpha.index.md"
        contents_after_first = target.read_text(encoding="utf-8")

        # Second pass with no legacy file present should be a no-op for
        # the migration step.
        graph2 = VaultGraph(tmp_path)
        result_second = check_structure(
            tmp_path, snapshot=graph2.to_snapshot(), fix=True
        )

        relocations = [
            d
            for d in result_second.diagnostics
            if d.path is not None
            and d.path.name == "alpha.index.md"
            and "Relocated" in d.message
        ]
        assert relocations == [], (
            "second --fix run must not perform any new relocations"
        )
        assert target.read_text(encoding="utf-8") == contents_after_first

    def test_fix_collision_reports_error(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        legacy = _write_legacy_index(tmp_path, "alpha")
        target_dir = tmp_path / ".vault" / "index"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "alpha.index.md"
        target.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# pre-existing\n",
            encoding="utf-8",
        )
        canonical_before = target.read_text(encoding="utf-8")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        collision_errors = [
            d
            for d in result.diagnostics
            if d.severity == Severity.ERROR and "already" in d.message
        ]
        assert collision_errors, "collision must surface an ERROR diagnostic"
        assert legacy.exists(), "legacy file must remain when target collides"
        assert target.read_text(encoding="utf-8") == canonical_before, (
            "canonical file must remain untouched on collision"
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
            or "legacy index" in d.message.lower()
        ]
        assert legacy_diags == [], (
            "canonical subfolder index must not trigger legacy diagnostics"
        )

    def test_no_duplicate_diagnostic_without_fix(self, tmp_path):
        # A root-level legacy index used to be reported twice: once by
        # the aggregate validator (pathless) and once by the per-file
        # migration helper. Operators saw two messages saying the same
        # thing. The check_structure pass must surface exactly one
        # actionable per-file ERROR diagnostic.
        _vault_with_minimal_skeleton(tmp_path)
        _write_legacy_index(tmp_path, "alpha")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=False)

        legacy_errors = [
            d
            for d in result.diagnostics
            if d.severity == Severity.ERROR
            and (
                "Legacy feature index" in d.message
                or "Misplaced feature index" in d.message
            )
        ]
        assert len(legacy_errors) == 1, (
            f"expected exactly one legacy/misplaced diagnostic per offence, "
            f"got {len(legacy_errors)}: {[d.message for d in legacy_errors]}"
        )
        assert legacy_errors[0].path is not None, (
            "the surviving diagnostic must be the actionable per-file message, "
            "not the pathless aggregate"
        )
        assert legacy_errors[0].fixable is True


class TestMigrateMisplacedIndexInSubdir:
    def test_reports_misplaced_index_in_typed_subdir(self, tmp_path):
        # An index file misplaced into a typed subdirectory (e.g.
        # ``adr/<feature>.index.md``) was previously a blind spot: the
        # filename-based exemption skipped it for frontmatter and
        # body-link checks while the migration helper only scanned the
        # docs root. The structure check must now flag it as a fixable
        # ERROR regardless of which subdir it lives in.
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
        assert any(d.severity == Severity.ERROR for d in misplaced_diags)
        assert any(d.fixable for d in misplaced_diags)
        assert misplaced.exists()

    def test_fix_relocates_misplaced_index_from_typed_subdir(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        misplaced = tmp_path / ".vault" / "plan" / "gamma.index.md"
        misplaced.write_text(
            "---\ngenerated: true\ntags:\n  - '#gamma'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# gamma\n",
            encoding="utf-8",
        )
        target = tmp_path / ".vault" / "index" / "gamma.index.md"

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        assert not misplaced.exists()
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert "'#index'" in text
        assert "'#gamma'" in text
        assert result.fixed_count >= 1

    def test_fix_preserves_crlf_content_during_migration(self, tmp_path):
        # A misplaced index with CRLF line endings must keep CRLF after
        # the migration inserts the #index tag. Mixed LF/CRLF inside
        # the same frontmatter block is the regression we are guarding
        # against.
        _vault_with_minimal_skeleton(tmp_path)
        misplaced = tmp_path / ".vault" / "delta.index.md"
        misplaced.write_bytes(
            b"---\r\n"
            b"generated: true\r\n"
            b"tags:\r\n"
            b"  - '#delta'\r\n"
            b"date: '2026-04-30'\r\n"
            b"related: []\r\n"
            b"---\r\n\r\n"
            b"# delta\r\n"
        )
        target = tmp_path / ".vault" / "index" / "delta.index.md"

        graph = VaultGraph(tmp_path)
        check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        raw = target.read_bytes()
        assert b"\r\n  - '#index'\r\n" in raw
        # No stray LF outside of CRLF pairs anywhere in the migrated file.
        without_crlf = raw.replace(b"\r\n", b"")
        assert b"\n" not in without_crlf

    def test_fix_collision_in_subdir_misplacement(self, tmp_path):
        _vault_with_minimal_skeleton(tmp_path)
        misplaced = tmp_path / ".vault" / "research" / "epsilon.index.md"
        misplaced.write_text(
            "---\ngenerated: true\ntags:\n  - '#epsilon'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# misplaced\n",
            encoding="utf-8",
        )
        target_dir = tmp_path / ".vault" / "index"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "epsilon.index.md"
        target.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#epsilon'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# pre-existing\n",
            encoding="utf-8",
        )
        canonical_before = target.read_text(encoding="utf-8")

        graph = VaultGraph(tmp_path)
        result = check_structure(tmp_path, snapshot=graph.to_snapshot(), fix=True)

        collision_errors = [
            d
            for d in result.diagnostics
            if d.severity == Severity.ERROR and "already" in d.message
        ]
        assert collision_errors
        assert misplaced.exists()
        assert target.read_text(encoding="utf-8") == canonical_before
