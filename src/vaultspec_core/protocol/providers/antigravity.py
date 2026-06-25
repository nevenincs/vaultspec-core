"""Antigravity execution provider for workspace-scoped prompts and rules.

This module implements the Google Antigravity provider within the shared
execution protocol. Antigravity consumes shared rules and skills from the
``.agents/`` tree and selects its active model at runtime (via the in-editor
model picker or ``agy --model``) rather than from a per-agent ``model`` field.
Its :class:`~vaultspec_core.core.enums.AntigravityModels` registry is therefore
reference-only and is never emitted into synced artifacts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

    from ...core.enums import ModelRegistry

from ...core.enums import AntigravityModels
from .base import (
    ExecutionProvider,
    resolve_includes,
)

__all__ = ["AntigravityProvider"]


class AntigravityProvider(ExecutionProvider):
    """Execution provider for Google Antigravity.

    Antigravity has no dedicated system-prompt file and no per-agent model
    field; it reads shared rules from ``.agents/rules/*.md``. Model choice is a
    runtime concern, so :attr:`models` is a reference registry only. Registered
    as ``"antigravity"`` in the provider registry.
    """

    @property
    def name(self) -> str:
        """Return the provider identifier string.

        Returns:
            The string ``"antigravity"``.
        """
        return "antigravity"

    @property
    def models(self) -> ModelRegistry:
        """Return the Antigravity reference model registry.

        Returns:
            The :class:`AntigravityModels` registry class. These identifiers
            are reference-only; Antigravity selects its model at runtime.
        """
        return AntigravityModels

    def load_system_prompt(self, root_dir: pathlib.Path) -> str:  # noqa: ARG002
        """Return an empty string; Antigravity has no dedicated system file.

        Args:
            root_dir: Workspace root directory (unused).

        Returns:
            An empty string. Antigravity carries instructions through shared
            rules rather than a standalone system prompt.
        """
        return ""

    def load_rules(self, root_dir: pathlib.Path) -> str:
        """Load and inline-resolve rules from ``.agents/rules/``.

        All ``*.md`` files in the shared rules directory are read in sorted
        order and their ``@include`` directives are resolved recursively.

        Args:
            root_dir: Workspace root directory.

        Returns:
            Concatenated rules text, or an empty string if the directory does
            not exist.
        """
        rules_dir = root_dir / ".agents" / "rules"
        if not rules_dir.exists():
            return ""

        all_rules = []
        for rule_file in sorted(rules_dir.glob("*.md")):
            content = rule_file.read_text(encoding="utf-8")
            resolved = resolve_includes(content, rules_dir, root_dir)
            all_rules.append(resolved)

        return "\n\n".join(all_rules)
