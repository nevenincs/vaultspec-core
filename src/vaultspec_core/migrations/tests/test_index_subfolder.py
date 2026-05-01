"""Tests for the first registry entry, ``index_subfolder``.

Exercises
:func:`vaultspec_core.migrations.m_0_1_17_index_subfolder.migrate`
against real on-disk fixtures. The migration relocates legacy
``<feature>.index.md`` files into ``.vault/index/`` and inserts the
``#index`` directory tag when missing. CRLF line endings are
preserved.

The detection counterpart in ``check_structure`` is exercised
separately in ``vaultcore/checks/tests/test_index_migration.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.migrations.m_0_1_17_index_subfolder import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


def _vault_skeleton(vault_root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (vault_root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


def _legacy_root_index(
    vault_root: Path,
    feature: str,
    *,
    include_index_tag: bool = False,
) -> Path:
    docs = vault_root / ".vault"
    docs.mkdir(parents=True, exist_ok=True)
    tag_lines = ["  - '#index'"] if include_index_tag else []
    tag_lines.append(f"  - '#{feature}'")
    tag_block = "\n".join(tag_lines)
    content = (
        "---\n"
        "generated: true\n"
        "tags:\n"
        f"{tag_block}\n"
        "date: '2026-04-30'\n"
        "related: []\n"
        "---\n\n"
        f"# `{feature}` feature index\n"
    )
    p = docs / f"{feature}.index.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestRelocatesLegacyRootIndex:
    def test_relocates_to_index_subfolder(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        legacy = _legacy_root_index(tmp_path, "alpha")
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        result = migrate(tmp_path)

        assert not legacy.exists()
        assert target.exists()
        assert result.counts["moved"] == 1
        assert "relocated 1" in result.summary

    def test_inserts_index_directory_tag(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        _legacy_root_index(tmp_path, "alpha", include_index_tag=False)
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        result = migrate(tmp_path)

        text = target.read_text(encoding="utf-8")
        assert "'#index'" in text
        assert "'#alpha'" in text
        assert result.counts["tagged"] == 1

    def test_skips_tag_insert_when_already_present(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        _legacy_root_index(tmp_path, "alpha", include_index_tag=True)
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        result = migrate(tmp_path)

        text = target.read_text(encoding="utf-8")
        # Exactly one #index occurrence, no double-insertion.
        assert text.count("'#index'") == 1
        assert result.counts["tagged"] == 0
        assert result.counts["moved"] == 1


class TestIdempotence:
    def test_already_migrated_is_noop(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        idx_dir = tmp_path / ".vault" / "index"
        idx_dir.mkdir(parents=True, exist_ok=True)
        canonical = idx_dir / "alpha.index.md"
        canonical.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha\n",
            encoding="utf-8",
        )
        before = canonical.read_text(encoding="utf-8")

        result = migrate(tmp_path)

        after = canonical.read_text(encoding="utf-8")
        assert before == after
        assert result.counts["moved"] == 0
        assert "no legacy" in result.summary

    def test_second_run_no_op(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        _legacy_root_index(tmp_path, "alpha")

        first = migrate(tmp_path)
        assert first.counts["moved"] == 1

        second = migrate(tmp_path)
        assert second.counts["moved"] == 0
        assert "no legacy" in second.summary

    def test_no_docs_dir_is_noop(self, tmp_path: Path):
        # Pure no-vault path; no .vault/ at all.
        result = migrate(tmp_path)
        assert result.counts["moved"] == 0
        assert "no .vault" in result.summary


class TestCRLFPreservation:
    def test_crlf_source_keeps_crlf_after_migration(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
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

        migrate(tmp_path)

        raw = target.read_bytes()
        assert b"\r\n  - '#index'\r\n" in raw
        # No bare LF outside CRLF pairs.
        assert b"\n" not in raw.replace(b"\r\n", b"")


class TestMisplacedInTypedSubdir:
    def test_relocates_from_subdir(self, tmp_path: Path):
        # Files mistakenly dropped into adr/, plan/, etc must also be
        # relocated. The pre-#91 codebase had a blind spot for these.
        _vault_skeleton(tmp_path)
        misplaced = tmp_path / ".vault" / "plan" / "gamma.index.md"
        misplaced.write_text(
            "---\ngenerated: true\ntags:\n  - '#gamma'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# gamma\n",
            encoding="utf-8",
        )
        target = tmp_path / ".vault" / "index" / "gamma.index.md"

        result = migrate(tmp_path)

        assert not misplaced.exists()
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert "'#index'" in text
        assert result.counts["moved"] == 1


class TestCollision:
    def test_target_collision_leaves_legacy_in_place(self, tmp_path: Path):
        _vault_skeleton(tmp_path)
        legacy = _legacy_root_index(tmp_path, "epsilon")
        idx_dir = tmp_path / ".vault" / "index"
        idx_dir.mkdir(parents=True, exist_ok=True)
        target = idx_dir / "epsilon.index.md"
        canonical_before = (
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#epsilon'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# pre-existing\n"
        )
        target.write_text(canonical_before, encoding="utf-8")

        result = migrate(tmp_path)

        assert legacy.exists()
        assert target.read_text(encoding="utf-8") == canonical_before
        assert result.counts["collisions"] == 1
        assert result.counts["moved"] == 0
