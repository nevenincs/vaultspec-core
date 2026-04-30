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
