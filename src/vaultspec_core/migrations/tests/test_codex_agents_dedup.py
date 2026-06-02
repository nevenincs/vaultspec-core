"""Tests for the ``codex_agents_dedup`` registry entry.

Exercises
:func:`vaultspec_core.migrations.m_0_1_24_codex_agents_dedup.migrate`
against real on-disk ``.codex/config.toml`` fixtures. The migration strips
stale duplicate ``[agents.*]`` tables that collide with the managed
``<vaultspec type="agents">`` block (issue #140) and leaves clean or
managed-block-less files untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.migrations.m_0_1_24_codex_agents_dedup import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


_MANAGED_BLOCK = (
    '# <vaultspec type="agents">\n'
    '[agents."vaultspec-worker"]\n'
    'description = "worker"\n'
    "prompt = '''\n"
    "Do the work.\n"
    "'''\n"
    "# </vaultspec>\n"
)


def _config(root: Path, content: str) -> Path:
    path = root / ".codex" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _agent_headers(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("[agents.")
    ]


class TestRemovesDuplicates:
    """Stale duplicate tables outside the managed block are removed."""

    def test_strips_raw_unwrapped_duplicate(self, tmp_path: Path):
        legacy = (
            "[agents.vaultspec-worker]\n"
            'description = "old"\n'
            'prompt = """\n[not a table]\n"""\n\n'
        )
        path = _config(tmp_path, legacy + _MANAGED_BLOCK)

        result = migrate(tmp_path)

        assert result.counts["deduped"] == 1
        headers = _agent_headers(path)
        assert headers == ['[agents."vaultspec-worker"]']

    def test_strips_legacy_sentinel_block(self, tmp_path: Path):
        legacy = (
            "# BEGIN VAULTSPEC MANAGED CODEX AGENTS\n"
            "[agents.vaultspec-worker]\n"
            'description = "old"\n'
            "# END VAULTSPEC MANAGED CODEX AGENTS\n\n"
        )
        path = _config(tmp_path, legacy + _MANAGED_BLOCK)

        result = migrate(tmp_path)

        assert result.counts["deduped"] == 1
        content = path.read_text(encoding="utf-8")
        assert "# BEGIN VAULTSPEC MANAGED CODEX AGENTS" not in content
        assert _agent_headers(path) == ['[agents."vaultspec-worker"]']

    def test_preserves_user_top_level_keys(self, tmp_path: Path):
        legacy = '[agents.vaultspec-worker]\ndescription = "old"\n\n'
        head = 'model = "gpt-5"\n\n'
        path = _config(tmp_path, head + legacy + _MANAGED_BLOCK)

        migrate(tmp_path)

        assert 'model = "gpt-5"' in path.read_text(encoding="utf-8")


class TestNoOp:
    """The migration is a true no-op on clean or unaffected workspaces."""

    def test_clean_managed_block_unchanged(self, tmp_path: Path):
        path = _config(tmp_path, _MANAGED_BLOCK)
        before = path.read_text(encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts["deduped"] == 0
        assert path.read_text(encoding="utf-8") == before

    def test_idempotent(self, tmp_path: Path):
        legacy = '[agents.vaultspec-worker]\ndescription = "old"\n\n'
        path = _config(tmp_path, legacy + _MANAGED_BLOCK)

        first = migrate(tmp_path)
        after_first = path.read_text(encoding="utf-8")
        second = migrate(tmp_path)

        assert first.counts["deduped"] == 1
        assert second.counts["deduped"] == 0
        assert path.read_text(encoding="utf-8") == after_first

    def test_missing_config_is_noop(self, tmp_path: Path):
        result = migrate(tmp_path)

        assert result.counts["deduped"] == 0
        assert "nothing to migrate" in result.summary

    def test_no_managed_block_leaves_unknown_tables(self, tmp_path: Path):
        # Without a managed block there is no canonical set to dedup against;
        # a lone raw table is not a duplicate, so it must be preserved.
        raw = '[agents.custom]\ndescription = "mine"\n'
        path = _config(tmp_path, raw)
        before = path.read_text(encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts["deduped"] == 0
        assert path.read_text(encoding="utf-8") == before
