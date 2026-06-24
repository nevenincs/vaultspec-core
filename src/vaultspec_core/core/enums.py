"""Define the canonical enum vocabulary shared across core configuration.

This module holds the stable symbolic names for tools, resource kinds,
filenames, directory names, and model capability tiers. It serves as a schema
layer for the rest of the package rather than a workflow or execution module.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class CapabilityLevel(IntEnum):
    """Tiered capability levels used to select an appropriate model."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @classmethod
    def from_tier(cls, tier: str | None) -> CapabilityLevel:
        """Resolve a persona ``tier:`` frontmatter string to a capability level.

        Agent personas author a coarse ``tier`` (``LOW``, ``STANDARD``,
        ``HIGH``) rather than a numeric level. ``STANDARD`` is the persona
        vocabulary for the middle tier and maps to :attr:`MEDIUM`; the legacy
        ``MEDIUM`` spelling is accepted for backwards compatibility. The match
        is case-insensitive and whitespace-tolerant.

        Args:
            tier: Raw ``tier`` value from persona frontmatter, or ``None``.

        Returns:
            The corresponding :class:`CapabilityLevel`; defaults to
            :attr:`MEDIUM` for any missing or unrecognized value.
        """
        normalized = (tier or "").strip().upper()
        aliases = {
            "LOW": cls.LOW,
            "STANDARD": cls.MEDIUM,
            "MEDIUM": cls.MEDIUM,
            "HIGH": cls.HIGH,
        }
        return aliases.get(normalized, cls.MEDIUM)


class _TieredModelRegistry(StrEnum):
    """Base for per-provider model registries keyed by capability tier.

    Each concrete registry declares ``HIGH``, ``MEDIUM``, and ``LOW`` members
    whose values are the provider's current model identifier strings. Members
    are named after :class:`CapabilityLevel` members so :meth:`from_level` can
    resolve a level to a model by name without a per-registry mapping table.
    """

    @classmethod
    def from_level(cls, level: CapabilityLevel) -> _TieredModelRegistry:
        """Return the model identifier for a given :class:`CapabilityLevel`.

        Args:
            level: Desired capability tier.

        Returns:
            The registry member whose name matches *level*; defaults to
            ``MEDIUM`` for any level without a matching member.
        """
        try:
            return cls[level.name]
        except KeyError:
            return cls["MEDIUM"]


class ClaudeModels(_TieredModelRegistry):
    """Single source of truth for Claude model identifiers.

    Verified against Anthropic's published model lineup (mid-2026): Opus 4.8
    is the current flagship, with Sonnet 4.6 and Haiku 4.5 as the mid and fast
    tiers respectively.
    """

    HIGH = "claude-opus-4-8"
    MEDIUM = "claude-sonnet-4-6"
    LOW = "claude-haiku-4-5"


class GeminiModels(_TieredModelRegistry):
    """Single source of truth for Gemini model identifiers.

    Verified against Google's published Gemini API model list (mid-2026). The
    prior ``gemini-3-pro-preview`` was shut down 2026-03-09, ``-3-flash-preview``
    was superseded, and ``gemini-2.5-flash`` is deprecated (shutdown
    2026-10-16); all three are replaced by the identifiers below.
    """

    HIGH = "gemini-3.1-pro-preview"
    MEDIUM = "gemini-3.5-flash"
    LOW = "gemini-3.1-flash-lite"


class CodexModels(_TieredModelRegistry):
    """Single source of truth for OpenAI Codex model identifiers.

    Verified against OpenAI's published Codex model list (mid-2026). ``gpt-5.5``
    is the recommended flagship default; the older ``gpt-5-codex`` family is
    deprecated (API shutdown 2026-07-23) in favour of ``gpt-5.5``. Reasoning
    depth is controlled separately via the Codex ``model_reasoning_effort``
    setting rather than a distinct per-tier model identifier.
    """

    HIGH = "gpt-5.5"
    MEDIUM = "gpt-5.4"
    LOW = "gpt-5.4-mini"


class AntigravityModels(_TieredModelRegistry):
    """Reference registry of model identifiers for Google Antigravity.

    Antigravity is model-optional and multi-vendor: the active model is chosen
    at runtime (``agy --model`` or the in-editor model picker), not codified in
    synced agent or skill files. Antigravity does not consume a ``model``
    frontmatter field, so this registry is reference-only and is never emitted
    into provider artifacts. The values mirror Antigravity's default
    Gemini-class lineup so a single source of truth still exists for tooling
    that wants to display or validate a default tier.
    """

    HIGH = "gemini-3.1-pro-preview"
    MEDIUM = "gemini-3.5-flash"
    LOW = "gemini-3.1-flash-lite"


ModelRegistry = (
    type[ClaudeModels]
    | type[GeminiModels]
    | type[CodexModels]
    | type[AntigravityModels]
)


class Tool(StrEnum):
    """Supported AI tool destinations."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"


class GeminiBuiltinTool(StrEnum):
    """Canonical Gemini CLI built-in tool identifiers.

    Each member's string value is the verbatim constant exported from
    ``packages/core/src/tools/definitions/base-declarations.ts`` in
    `google-gemini/gemini-cli`. The Gemini agent definition validator
    (`packages/core/src/agents/agentLoader.ts`) calls
    ``isValidToolName`` against these strings; any drift causes
    ``Invalid tool name`` errors at agent load time.

    Drift is guarded at test time by the live source-pin test
    (``tests/cli/test_agents_render.py::TestUpstreamGeminiToolPin``),
    which fetches ``base-declarations.ts`` from the upstream main
    branch and asserts every enum value matches the upstream constant.
    """

    GLOB = "glob"
    GREP_SEARCH = "grep_search"
    READ_FILE = "read_file"
    RUN_SHELL_COMMAND = "run_shell_command"
    WRITE_FILE = "write_file"
    REPLACE = "replace"
    GOOGLE_WEB_SEARCH = "google_web_search"
    WEB_FETCH = "web_fetch"


class ProviderCapability(StrEnum):
    """Capabilities a provider can declare support for."""

    RULES = "rules"
    SKILLS = "skills"
    AGENTS = "agents"
    ROOT_CONFIG = "root_config"
    SYSTEM = "system"
    HOOKS = "hooks"
    TEAMS = "teams"
    SCHEDULED_TASKS = "scheduled_tasks"
    WORKFLOWS = "workflows"


class Resource(StrEnum):
    """Managed spec resource types."""

    RULES = "rules"
    AGENTS = "agents"
    SKILLS = "skills"
    SYSTEM = "system"
    TEMPLATES = "templates"
    HOOKS = "hooks"
    WORKFLOWS = "workflows"
    MCPS = "mcps"


class FileName(StrEnum):
    """Canonical filenames for framework documentation and configuration."""

    CONFIG_TOML = "config.toml"
    CLAUDE = "CLAUDE.md"
    GEMINI = "GEMINI.md"
    AGENTS = "AGENTS.md"
    SKILL = "SKILL.md"
    SYSTEM = "SYSTEM.md"
    MCP_CONFIG = "mcp_config.json"


class DirName(StrEnum):
    """Reserved directory names within the workspace.

    The names prefixed with ``.`` are top-level workspace directories
    (``.vault``, ``.vaultspec``, provider directories). :attr:`INDEX` is
    a child directory under :attr:`VAULT` that holds auto-generated
    feature index files.
    """

    VAULT = ".vault"
    VAULTSPEC = ".vaultspec"
    CLAUDE = ".claude"
    GEMINI = ".gemini"
    ANTIGRAVITY = ".agents"
    CODEX = ".codex"
    INDEX = "index"


class ManagedState(StrEnum):
    """Desired state of a managed workspace artifact."""

    PRESENT = "present"
    ABSENT = "absent"


class CliAction(StrEnum):
    """CLI action passed to the resolver and preflight engine."""

    INSTALL = "install"
    UPGRADE = "upgrade"
    SYNC = "sync"
    UNINSTALL = "uninstall"
    DOCTOR = "doctor"


class PrecommitHook(StrEnum):
    """Canonical pre-commit hook IDs managed by vaultspec-core.

    ``VAULT_FIX`` runs all vault checkers with ``--fix``, auto-repairing
    safe issues (naming, frontmatter, annotations, links, dangling,
    references, schema) and blocking on remaining errors (body-links).

    ``VAULT_SANITIZE_ANNOTATIONS`` runs the explicit annotation sanitizer so
    generated vault documents do not commit template-only guidance.

    ``SPEC_CHECK`` runs the workspace doctor, diagnosing framework,
    provider, and tooling health.

    ``CHECK_PROVIDER_ARTIFACTS`` prevents provider artifacts and
    installation manifests from being committed to git.
    """

    VAULT_FIX = "vault-fix"
    VAULT_SANITIZE_ANNOTATIONS = "vault-sanitize-annotations"
    SPEC_CHECK = "spec-check"
    CHECK_PROVIDER_ARTIFACTS = "check-provider-artifacts"
