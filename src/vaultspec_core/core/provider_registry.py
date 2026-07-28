"""Provider vocabulary and shared validation helpers for the command surface.

Hosts the provider-name vocabulary (the argument names accepted by
install/uninstall/sync), the relative-path helper used throughout the command
implementations, and the small validation helpers every command surface
shares. This module has no dependencies on the other ``core`` command
implementation modules, so it sits at the bottom of their internal
dependency graph.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from . import types as _t
from .enums import Tool
from .exceptions import ProviderError, VaultSpecError

#: Re-exported (with underscore intact) for the sibling command modules that
#: reach into this as the single public import surface for provider vocabulary.
__all__ = ["_PROVIDER_TO_TOOLS"]

# Map provider argument names to Tool enum members. The per-tool entries derive
# from the Tool enum so adding a provider is a single-site change; "all" selects
# every tool and "core" selects none (framework-only). VALID_PROVIDERS and
# SYNC_PROVIDERS are derived from this map so the provider vocabulary has one
# source of truth.
_PROVIDER_TO_TOOLS: dict[str, list[Tool]] = {t.value: [t] for t in Tool}
_PROVIDER_TO_TOOLS["all"] = list(Tool)
_PROVIDER_TO_TOOLS["core"] = []

# Valid provider arguments for install/uninstall commands (every selector).
VALID_PROVIDERS = set(_PROVIDER_TO_TOOLS)

# Valid sync provider targets exposed to the CLI.
SYNC_PROVIDERS = VALID_PROVIDERS - {"core"}


def rel(target: Path, p: Path) -> str:
    return str(p.relative_to(target)).replace("\\", "/")


def validate_provider(provider: str) -> None:
    """Validate that *provider* is a known provider name.

    Raises:
        ProviderError: If *provider* is not in :data:`VALID_PROVIDERS`.
    """
    if provider not in VALID_PROVIDERS:
        raise ProviderError(
            f"Unknown provider '{provider}'. "
            f"Valid: {', '.join(sorted(VALID_PROVIDERS))}"
        )


def validate_skip(skip: set[str] | None, *, allow_core: bool = True) -> set[str]:
    """Validate and normalise a *skip* set.

    Raises:
        ProviderError: If any value in *skip* is not a valid component name.
    """
    if not skip:
        return set()
    # "all" is not a valid skip target  - you'd just not run the command.
    # "mcp" is a valid skip target but is not a provider.
    allowed = (VALID_PROVIDERS - {"all"}) | {"mcp", "precommit"}
    if not allow_core:
        allowed.discard("core")
    bad = skip - allowed
    if bad:
        raise ProviderError(
            f"Invalid --skip value(s): {', '.join(sorted(bad))}. "
            f"Valid: {', '.join(sorted(allowed))}"
        )
    return skip


def filter_tools(tools: list[Tool], skip: set[str]) -> list[Tool]:
    """Remove tools whose provider name is in *skip*."""
    if not skip:
        return tools
    return [t for t in tools if t.value not in skip]


def require_reconciliation_success(
    results: _t.SyncResult | Iterable[_t.SyncResult],
    *,
    operation: str,
) -> None:
    """Refuse to report install success after a failed reconciliation pass."""
    passes = (results,) if isinstance(results, _t.SyncResult) else tuple(results)
    errors = [message for result in passes for message in result.errors]
    unreported = sum(result.errored for result in passes) - len(errors)
    if unreported > 0:
        errors.append(f"{unreported} reconciliation error(s) had no detail message.")
    if errors:
        raise VaultSpecError(
            f"{operation} failed.",
            hint=" ".join(errors),
        )


# Backward-compatible private aliases: several ``core`` modules outside this
# round's scope still import these helpers by their original underscore
# names (e.g. ``core/commands.py``'s re-export surface, ``core/provision.py``,
# ``core/scaffold.py``, ``core/uninstall.py``). Keep them resolvable without
# touching those call sites; new callers should prefer the public names.
_rel = rel
_validate_provider = validate_provider
_validate_skip = validate_skip
_filter_tools = filter_tools
_require_reconciliation_success = require_reconciliation_success
