"""Public surface for the vaultspec-core execution protocol.

Exports the shared provider contract
(:class:`~vaultspec_core.protocol.providers.base.ExecutionProvider`), the
concrete providers, model registries
(:class:`~vaultspec_core.protocol.providers.ClaudeModels`,
:class:`~vaultspec_core.protocol.providers.GeminiModels`,
:class:`~vaultspec_core.protocol.providers.CodexModels`,
:class:`~vaultspec_core.protocol.providers.AntigravityModels`), and
:class:`~vaultspec_core.protocol.providers.CapabilityLevel`
from :mod:`.providers`.  Sits above :mod:`vaultspec_core.core.enums`;
consumed by :mod:`vaultspec_core.cli`.
"""

from .providers import AntigravityModels as AntigravityModels
from .providers import AntigravityProvider as AntigravityProvider
from .providers import CapabilityLevel as CapabilityLevel
from .providers import ClaudeModels as ClaudeModels
from .providers import ClaudeProvider as ClaudeProvider
from .providers import CodexModels as CodexModels
from .providers import CodexProvider as CodexProvider
from .providers import ExecutionProvider as ExecutionProvider
from .providers import GeminiModels as GeminiModels
from .providers import GeminiProvider as GeminiProvider

__all__ = [
    "AntigravityModels",
    "AntigravityProvider",
    "CapabilityLevel",
    "ClaudeModels",
    "ClaudeProvider",
    "CodexModels",
    "CodexProvider",
    "ExecutionProvider",
    "GeminiModels",
    "GeminiProvider",
]
