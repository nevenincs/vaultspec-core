"""Tests for the ``gitignore_reversal`` registry entry.

Exercises
:func:`vaultspec_core.migrations.m_0_1_20_gitignore_reversal.migrate`
against real on-disk ``.gitignore`` fixtures. The migration rewrites a
stock pre-reversal managed block to the team-shared spec-layer policy and
conservatively leaves an operator-customised block untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.gitignore import MARKER_BEGIN, MARKER_END
from vaultspec_core.migrations.m_0_1_20_gitignore_reversal import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


# A representative pre-reversal managed block: blanket-ignores the spec
# layer, the MCP config, and a generated provider directory and file.
_OLD_BLOCK = [
    ".mcp.json",
    ".vaultspec/",
    ".vaultspec/*.lock",
    ".vaultspec/_snapshots/",
    ".vaultspec/providers.json",
    ".vault/.obsidian/",
    ".vault/.trash/",
    ".vault/data/",
    ".vault/logs/",
    ".claude/",
    "CLAUDE.md",
]


def _workspace(root: Path, block: list[str] | None) -> Path:
    """Create an installed-style workspace with a managed gitignore block.

    Passing ``block=None`` writes a ``.gitignore`` with no managed block.
    """
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    (root / ".vault").mkdir(parents=True, exist_ok=True)
    lines = ["# user-owned section", "node_modules/", ""]
    if block is not None:
        lines += [MARKER_BEGIN, *block, MARKER_END]
    (root / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _block_entries(root: Path) -> list[str]:
    """Return the entries inside the managed block of ``root/.gitignore``."""
    lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    begin = lines.index(MARKER_BEGIN)
    end = lines.index(MARKER_END)
    return [line.strip() for line in lines[begin + 1 : end] if line.strip()]


class TestRewritesStockBlock:
    """A stock pre-reversal block is rewritten to the team-shared policy."""

    def test_drops_blanket_spec_layer_and_provider_entries(self, tmp_path: Path):
        _workspace(tmp_path, _OLD_BLOCK)

        result = migrate(tmp_path)

        assert result.counts["rewritten"] == 1
        entries = _block_entries(tmp_path)
        # Authored content is no longer ignored.
        assert ".vaultspec/" not in entries
        assert ".mcp.json" not in entries
        assert ".claude/" not in entries
        assert "CLAUDE.md" not in entries

    def test_keeps_runtime_byproducts_ignored(self, tmp_path: Path):
        _workspace(tmp_path, _OLD_BLOCK)

        migrate(tmp_path)

        entries = _block_entries(tmp_path)
        assert ".vaultspec/_snapshots/" in entries
        assert ".vaultspec/*.lock" in entries
        assert ".vaultspec/providers.json" in entries
        assert ".vault/logs/" in entries

    def test_preserves_user_owned_lines(self, tmp_path: Path):
        _workspace(tmp_path, _OLD_BLOCK)

        migrate(tmp_path)

        text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        # Lines outside the managed block are never touched.
        assert "node_modules/" in text

    def test_second_run_is_noop(self, tmp_path: Path):
        _workspace(tmp_path, _OLD_BLOCK)

        migrate(tmp_path)
        second = migrate(tmp_path)

        # The block now matches the reversed policy; nothing to rewrite.
        assert second.counts["rewritten"] == 0
        assert second.counts["skipped"] == 0


class TestConservativeWithOperatorEdits:
    """A block carrying an unrecognised entry is left untouched."""

    def test_operator_customised_block_is_preserved(self, tmp_path: Path):
        custom = [*_OLD_BLOCK, "secrets/local-only.env"]
        _workspace(tmp_path, custom)

        result = migrate(tmp_path)

        assert result.counts["skipped"] == 1
        assert result.counts["rewritten"] == 0
        # The block - including the operator's own line - is intact.
        entries = _block_entries(tmp_path)
        assert "secrets/local-only.env" in entries
        assert ".vaultspec/" in entries

    def test_summary_directs_operator_to_reconcile(self, tmp_path: Path):
        custom = [*_OLD_BLOCK, "secrets/local-only.env"]
        _workspace(tmp_path, custom)

        result = migrate(tmp_path)

        assert "reconcile" in result.summary


class TestNoopCases:
    """Workspaces with nothing for this migration to do."""

    def test_no_gitignore_is_noop(self, tmp_path: Path):
        (tmp_path / ".vaultspec").mkdir()

        result = migrate(tmp_path)

        assert result.counts == {"rewritten": 0, "skipped": 0, "nested_gitignore": 0}
        assert "nothing to migrate" in result.summary

    def test_no_managed_block_is_noop(self, tmp_path: Path):
        _workspace(tmp_path, block=None)

        result = migrate(tmp_path)

        assert result.counts == {"rewritten": 0, "skipped": 0, "nested_gitignore": 0}
        assert "nothing to migrate" in result.summary
