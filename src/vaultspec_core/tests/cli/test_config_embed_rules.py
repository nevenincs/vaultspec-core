"""Tests for rule delivery into provider root config files.

Antigravity (`agy`) reads ``GEMINI.md`` prose but does not expand Gemini
``@rules/`` includes, so its rules must be embedded inline. Claude Code and
gemini-cli expand ``@`` includes, so ``CLAUDE.md`` keeps reference lines. These
tests run a real install and assert each config file uses the right form.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

# An @-include line inside a managed config block (e.g. "@.agents/rules/x.md").
_INCLUDE_LINE = re.compile(r"^@[\w./-]+\.md$", re.MULTILINE)


class TestAgyRuleEmbedding:
    def test_gemini_md_embeds_rules_without_includes(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all")
        gemini_md = (tmp_path / "GEMINI.md").read_text(encoding="utf-8")
        assert "## Vaultspec Rules" in gemini_md
        # agy ignores @ includes, so GEMINI.md must carry no include lines.
        assert not _INCLUDE_LINE.search(gemini_md), (
            "GEMINI.md still contains @rules includes, which agy silently drops"
        )

    def test_gemini_md_contains_actual_rule_content(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all")
        gemini_md = (tmp_path / "GEMINI.md").read_text(encoding="utf-8")
        # The embedded body must reproduce a synced rule file's content, not
        # merely reference it.
        rules_dir = tmp_path / ".agents" / "rules"
        rule_files = sorted(rules_dir.glob("*.md"))
        assert rule_files, "no synced agy rules to embed"
        # A distinctive non-trivial line from the first rule should appear.
        sample_lines = [
            ln.strip()
            for ln in rule_files[0].read_text(encoding="utf-8").splitlines()
            if len(ln.strip()) > 40 and not ln.strip().startswith(("#", "<!--", "---"))
        ]
        assert sample_lines, "rule file had no substantive line to assert on"
        assert sample_lines[0] in gemini_md

    def test_claude_md_keeps_include_references(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all")
        claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        # Claude Code expands @ imports, so CLAUDE.md should still reference.
        assert _INCLUDE_LINE.search(claude_md), (
            "CLAUDE.md should keep @rules include lines (Claude expands them)"
        )
