"""Codex execution provider for workspace-scoped prompts and rules.

This module implements the OpenAI Codex provider within the shared execution
protocol. Codex reads its project instructions from a root ``AGENTS.md`` file
and its managed rules from ``.codex/rules/*.md``; agent definitions and model
selection are codified in ``.codex/config.toml`` by the sync engine rather than
in per-agent files. This provider preserves the shared protocol semantics,
result types, and capability-tier model selection defined by the base layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

    from ...core.enums import ModelRegistry

from ...core.enums import CodexModels
from .base import (
    ExecutionProvider,
    resolve_includes,
)

__all__ = ["CodexProvider"]


class CodexProvider(ExecutionProvider):
    """Execution provider for OpenAI Codex models.

    Loads system prompt from the root ``AGENTS.md`` and rules from
    ``.codex/rules/*.md`` with ``@include`` directives resolved via
    :func:`~vaultspec_core.protocol.providers.base.resolve_includes`.
    Registered as ``"codex"`` in the provider registry.
    """

    @property
    def name(self) -> str:
        """Return the provider identifier string.

        Returns:
            The string ``"codex"``.
        """
        return "codex"

    @property
    def models(self) -> ModelRegistry:
        """Return the Codex model registry.

        Returns:
            The :class:`CodexModels` registry class.
        """
        return CodexModels

    def load_system_prompt(self, root_dir: pathlib.Path) -> str:
        """Load the root ``AGENTS.md`` if it exists (deployed by CLI sync).

        Args:
            root_dir: Workspace root directory.

        Returns:
            File contents as a string, or an empty string if the file is absent.
        """
        system_file = root_dir / "AGENTS.md"
        if not system_file.exists():
            return ""
        return system_file.read_text(encoding="utf-8")

    def load_rules(self, root_dir: pathlib.Path) -> str:
        """Load and inline-resolve rules from ``.codex/rules/``.

        All ``*.md`` files in the rules directory are read in sorted order and
        their ``@include`` directives are resolved recursively.

        Args:
            root_dir: Workspace root directory.

        Returns:
            Concatenated rules text, or an empty string if the directory does
            not exist.
        """
        rules_dir = root_dir / ".codex" / "rules"
        if not rules_dir.exists():
            return ""

        all_rules = []
        for rule_file in sorted(rules_dir.glob("*.md")):
            content = rule_file.read_text(encoding="utf-8")
            resolved = resolve_includes(content, rules_dir, root_dir)
            all_rules.append(resolved)

        return "\n\n".join(all_rules)
