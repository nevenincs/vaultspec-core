"""Behavioral tests for the execution protocol provider layer.

Covers include resolution, prompt section ordering, Claude prompt
loading, and the shared abstract provider API.
"""

from __future__ import annotations

import inspect

import pytest

from ..providers import (
    ClaudeProvider,
    ExecutionProvider,
    GeminiProvider,
    resolve_includes,
)

pytestmark = [pytest.mark.unit]


class TestSharedResolveIncludes:
    """Tests for :func:`~vaultspec_core.protocol.providers.base.resolve_includes`."""

    def test_basic(self, tmp_path):
        (tmp_path / "included.md").write_text("Included content", encoding="utf-8")
        result = resolve_includes("Before\n@included.md\nAfter", tmp_path, tmp_path)
        assert "Included content" in result
        assert "Before" in result
        assert "After" in result

    def test_missing_file(self, tmp_path):
        result = resolve_includes("@nonexistent.md", tmp_path, tmp_path)
        assert "ERROR: Missing include" in result

    def test_url_passthrough(self, tmp_path):
        result = resolve_includes("@https://example.com/file.md", tmp_path, tmp_path)
        assert "@https://example.com/file.md" in result


class TestGeminiProvider:
    """Tests for :class:`~vaultspec_core.protocol.providers.gemini.GeminiProvider`."""

    @pytest.fixture
    def provider(self):
        return GeminiProvider()

    def test_name(self, provider):
        assert provider.name == "gemini"

    def test_system_prompt_ordering(self, provider):
        """Prompt ordering: system instructions -> persona -> rules."""
        prompt = provider.construct_system_prompt(
            "I am a persona",
            "These are rules",
            "These are instructions",
        )
        instr_pos = prompt.index("SYSTEM INSTRUCTIONS")
        persona_pos = prompt.index("INSTRUCTIONS")
        rules_pos = prompt.index("SYSTEM RULES & CONTEXT")
        assert instr_pos < persona_pos < rules_pos


class TestClaudeProvider:
    """Tests for :class:`~vaultspec_core.protocol.providers.claude.ClaudeProvider`."""

    @pytest.fixture
    def provider(self):
        return ClaudeProvider()

    def test_name(self, provider):
        assert provider.name == "claude"


class TestProviderAPIParity:
    """Verify both providers implement the same abstract API."""

    def test_construct_system_prompt_signature_matches(self):
        """Both providers have the same construct_system_prompt signature."""
        claude_sig = inspect.signature(ClaudeProvider.construct_system_prompt)
        gemini_sig = inspect.signature(GeminiProvider.construct_system_prompt)
        assert list(claude_sig.parameters) == list(gemini_sig.parameters)

    def test_load_system_prompt_exists_on_both(self):
        """Both providers have load_system_prompt()."""
        assert hasattr(ClaudeProvider, "load_system_prompt")
        assert hasattr(GeminiProvider, "load_system_prompt")

    def test_load_rules_exists_on_both(self):
        """Both providers have load_rules()."""
        assert hasattr(ClaudeProvider, "load_rules")
        assert hasattr(GeminiProvider, "load_rules")

    def test_abstract_methods_on_base(self):
        """Base class declares expected abstract methods."""
        abstracts = ExecutionProvider.__abstractmethods__
        for method in (
            "load_system_prompt",
            "load_rules",
        ):
            assert method in abstracts


class TestClaudeSystemPrompt:
    """Verify Claude provider system prompt methods."""

    @pytest.fixture
    def provider(self):
        return ClaudeProvider()

    def test_load_system_prompt_reads_claude_md(self, provider, tmp_path):
        """load_system_prompt reads .claude/CLAUDE.md."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text(
            "System instructions here.",
            encoding="utf-8",
        )
        result = provider.load_system_prompt(tmp_path)
        assert "System instructions here." in result

    def test_load_system_prompt_missing_file(self, provider, tmp_path):
        """load_system_prompt returns '' when file is missing."""
        assert provider.load_system_prompt(tmp_path) == ""

    def test_construct_system_prompt_ordering(self, provider):
        """Prompt ordering: system instructions -> persona -> rules."""
        prompt = provider.construct_system_prompt(
            "I am a persona",
            "These are rules",
            "These are instructions",
        )
        instr_pos = prompt.index("SYSTEM INSTRUCTIONS")
        persona_pos = prompt.index("INSTRUCTIONS")
        rules_pos = prompt.index("SYSTEM RULES & CONTEXT")
        assert instr_pos < persona_pos < rules_pos

    def test_construct_system_prompt_no_instructions(self, provider):
        """Without system_instructions, no SYSTEM INSTRUCTIONS section."""
        prompt = provider.construct_system_prompt("persona", "rules", "")
        assert "SYSTEM INSTRUCTIONS" not in prompt
        assert "INSTRUCTIONS" in prompt
