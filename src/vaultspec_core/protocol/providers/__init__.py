"""Execution-provider implementations and shared exports.

Re-exports :class:`~vaultspec_core.protocol.providers.base.ExecutionProvider`,
:func:`~vaultspec_core.protocol.providers.base.resolve_includes`,
:func:`~vaultspec_core.protocol.providers.base.resolve_executable`, the concrete
providers (:class:`~vaultspec_core.protocol.providers.claude.ClaudeProvider`,
:class:`~vaultspec_core.protocol.providers.gemini.GeminiProvider`,
:class:`~vaultspec_core.protocol.providers.codex.CodexProvider`,
:class:`~vaultspec_core.protocol.providers.antigravity.AntigravityProvider`),
and the model registries (:class:`~vaultspec_core.core.enums.ClaudeModels`,
:class:`~vaultspec_core.core.enums.GeminiModels`,
:class:`~vaultspec_core.core.enums.CodexModels`,
:class:`~vaultspec_core.core.enums.AntigravityModels`,
:class:`~vaultspec_core.core.enums.CapabilityLevel`) from
:mod:`vaultspec_core.core.enums`. Consumed by :mod:`vaultspec_core.protocol`.
"""

from ...core.enums import AntigravityModels as AntigravityModels
from ...core.enums import CapabilityLevel as CapabilityLevel
from ...core.enums import ClaudeModels as ClaudeModels
from ...core.enums import CodexModels as CodexModels
from ...core.enums import GeminiModels as GeminiModels
from ...core.enums import ModelRegistry as ModelRegistry
from .antigravity import AntigravityProvider as AntigravityProvider
from .base import ExecutionProvider as ExecutionProvider
from .base import resolve_executable as resolve_executable
from .base import resolve_includes as resolve_includes
from .claude import ClaudeProvider as ClaudeProvider
from .codex import CodexProvider as CodexProvider
from .gemini import GeminiProvider as GeminiProvider
