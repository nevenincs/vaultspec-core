"""Tests for the per-provider model registries and capability mapping.

Covers :class:`~vaultspec_core.core.enums.CapabilityLevel` tier resolution and
the four tiered model registries (:class:`ClaudeModels`, :class:`GeminiModels`,
:class:`CodexModels`, :class:`AntigravityModels`): tier-name parity, level
lookup, and the pinned ground-truth identifier values.

The pinned-value tests are intentional change-detectors: when a provider ships
a new model the identifier here must be updated in lockstep, keeping the
registries the single source of truth for the model landscape.
"""

from __future__ import annotations

import pytest

from vaultspec_core.core.enums import (
    AntigravityModels,
    CapabilityLevel,
    ClaudeModels,
    CodexModels,
    GeminiModels,
)

pytestmark = [pytest.mark.unit]

_REGISTRIES = (ClaudeModels, GeminiModels, CodexModels, AntigravityModels)


class TestCapabilityLevelFromTier:
    @pytest.mark.parametrize(
        ("tier", "expected"),
        [
            ("LOW", CapabilityLevel.LOW),
            ("low", CapabilityLevel.LOW),
            ("STANDARD", CapabilityLevel.MEDIUM),
            ("standard", CapabilityLevel.MEDIUM),
            ("MEDIUM", CapabilityLevel.MEDIUM),
            ("HIGH", CapabilityLevel.HIGH),
            ("  High  ", CapabilityLevel.HIGH),
        ],
    )
    def test_known_tiers_resolve(self, tier: str, expected: CapabilityLevel):
        assert CapabilityLevel.from_tier(tier) is expected

    @pytest.mark.parametrize("tier", [None, "", "   ", "bogus", "L2"])
    def test_unknown_and_missing_default_to_medium(self, tier):
        assert CapabilityLevel.from_tier(tier) is CapabilityLevel.MEDIUM


class TestRegistryTierParity:
    """Every registry must expose a member for each capability level by name."""

    @pytest.mark.parametrize("registry", _REGISTRIES, ids=lambda r: r.__name__)
    def test_has_all_tier_members(self, registry):
        names = {m.name for m in registry}
        assert names == {"HIGH", "MEDIUM", "LOW"}

    @pytest.mark.parametrize("registry", _REGISTRIES, ids=lambda r: r.__name__)
    @pytest.mark.parametrize("level", list(CapabilityLevel))
    def test_from_level_matches_member_name(self, registry, level: CapabilityLevel):
        assert registry.from_level(level) is registry[level.name]


class TestGroundTruthIdentifiers:
    """Pinned model identifiers (verified mid-2026). Update in lockstep."""

    def test_claude_identifiers(self):
        assert ClaudeModels.HIGH == "claude-opus-4-8"
        assert ClaudeModels.MEDIUM == "claude-sonnet-4-6"
        assert ClaudeModels.LOW == "claude-haiku-4-5"

    def test_gemini_identifiers(self):
        assert GeminiModels.HIGH == "gemini-3.1-pro-preview"
        assert GeminiModels.MEDIUM == "gemini-3.5-flash"
        assert GeminiModels.LOW == "gemini-3.1-flash-lite"

    def test_codex_identifiers(self):
        assert CodexModels.HIGH == "gpt-5.5"
        assert CodexModels.MEDIUM == "gpt-5.4"
        assert CodexModels.LOW == "gpt-5.4-mini"

    def test_antigravity_identifiers_mirror_gemini_defaults(self):
        # Antigravity defaults to the Gemini-class lineup; the registry is
        # reference-only and never emitted into synced artifacts.
        assert AntigravityModels.HIGH.value == GeminiModels.HIGH.value
        assert AntigravityModels.MEDIUM.value == GeminiModels.MEDIUM.value
        assert AntigravityModels.LOW.value == GeminiModels.LOW.value

    @pytest.mark.parametrize("registry", _REGISTRIES, ids=lambda r: r.__name__)
    def test_no_deprecated_identifiers_remain(self, registry):
        # Strings shut down or deprecated by their vendors as of mid-2026.
        dead = {
            "claude-opus-4-6",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gpt-5-codex",
            "gpt-5",
        }
        assert not (dead & {m.value for m in registry})
