"""Behavioral tests for the execution protocol provider layer.

Covers include resolution, prompt section ordering, Claude prompt
loading, and the shared abstract provider API.
"""

from __future__ import annotations

import inspect

import pytest

from ..providers import (
    AntigravityModels,
    AntigravityProvider,
    ClaudeModels,
    ClaudeProvider,
    CodexModels,
    CodexProvider,
    ExecutionProvider,
    GeminiModels,
    GeminiProvider,
    resolve_includes,
)

pytestmark = [pytest.mark.unit]

_ALL_PROVIDERS = (
    ClaudeProvider,
    GeminiProvider,
    CodexProvider,
    AntigravityProvider,
)


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


class TestCodexProvider:
    """Tests for :class:`~vaultspec_core.protocol.providers.codex.CodexProvider`."""

    @pytest.fixture
    def provider(self):
        return CodexProvider()

    def test_name(self, provider):
        assert provider.name == "codex"

    def test_models_registry(self, provider):
        assert provider.models is CodexModels

    def test_load_system_prompt_reads_root_agents_md(self, provider, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Codex instructions.", encoding="utf-8")
        assert "Codex instructions." in provider.load_system_prompt(tmp_path)

    def test_load_system_prompt_missing_file(self, provider, tmp_path):
        assert provider.load_system_prompt(tmp_path) == ""

    def test_load_rules_reads_codex_rules(self, provider, tmp_path):
        rules_dir = tmp_path / ".codex" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "a.md").write_text("Rule A", encoding="utf-8")
        assert "Rule A" in provider.load_rules(tmp_path)

    def test_load_rules_missing_dir(self, provider, tmp_path):
        assert provider.load_rules(tmp_path) == ""


class TestAntigravityProvider:
    """Tests for the Antigravity provider (reference-only model registry)."""

    @pytest.fixture
    def provider(self):
        return AntigravityProvider()

    def test_name(self, provider):
        assert provider.name == "antigravity"

    def test_models_registry_is_reference_only(self, provider):
        assert provider.models is AntigravityModels

    def test_no_dedicated_system_prompt(self, provider, tmp_path):
        # Antigravity has no system file; model is runtime-selected.
        assert provider.load_system_prompt(tmp_path) == ""

    def test_load_rules_reads_shared_agents_rules(self, provider, tmp_path):
        rules_dir = tmp_path / ".agents" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "a.md").write_text("Shared rule", encoding="utf-8")
        assert "Shared rule" in provider.load_rules(tmp_path)

    def test_load_rules_missing_dir(self, provider, tmp_path):
        assert provider.load_rules(tmp_path) == ""


class TestProviderAPIParity:
    """Verify all providers implement the same abstract API."""

    def test_construct_system_prompt_signature_matches(self):
        """All providers share the construct_system_prompt signature."""
        baseline = list(
            inspect.signature(ClaudeProvider.construct_system_prompt).parameters
        )
        for provider_cls in _ALL_PROVIDERS:
            sig = inspect.signature(provider_cls.construct_system_prompt)
            assert list(sig.parameters) == baseline

    def test_load_system_prompt_exists_on_all(self):
        """Every provider has load_system_prompt()."""
        for provider_cls in _ALL_PROVIDERS:
            assert hasattr(provider_cls, "load_system_prompt")

    def test_load_rules_exists_on_all(self):
        """Every provider has load_rules()."""
        for provider_cls in _ALL_PROVIDERS:
            assert hasattr(provider_cls, "load_rules")

    def test_name_and_models_on_all(self):
        """Every provider exposes a name and a model registry."""
        expected_registry = {
            ClaudeProvider: ClaudeModels,
            GeminiProvider: GeminiModels,
            CodexProvider: CodexModels,
            AntigravityProvider: AntigravityModels,
        }
        for provider_cls, registry in expected_registry.items():
            instance = provider_cls()
            assert isinstance(instance.name, str) and instance.name
            assert instance.models is registry

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
