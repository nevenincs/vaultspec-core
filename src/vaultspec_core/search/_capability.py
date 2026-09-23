"""Which vault discovery this workspace can run, as orientation reports it.

Two independent facts, each read from local configuration and neither a
liveness check: whether hosted search has a credential, and whether the
semantic-search companion is provisioned. ``vaultspec-core status`` and the
MCP ``status`` tool both report them through :func:`discovery_fields`.

Hosted search is enrolled by one variable,
:data:`~vaultspec_core.config.VAULTSPEC_CORE_TYPESAFE_API_KEY`, resolved by
the configuration layer's credential resolver. Status surfaces report only
whether a key is configured and from which source, never the key.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import (
    VAULTSPEC_CORE_TYPESAFE_API_KEY,
    HostedSearchConfig,
    resolve_credential,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from ..core.diagnosis.collectors_companion import CompanionCapability

__all__ = [
    "DiscoveryCapability",
    "discovery_capability",
    "discovery_fields",
    "hosted_search_config",
]


def hosted_search_config(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    interpreter_prefix: Path | None = None,
) -> HostedSearchConfig:
    """Report whether hosted search is configured for *root*, never the key.

    This is local configuration, not liveness: a configured key may still be
    rejected by the provider.

    Args:
        root: The workspace root.
        environ: The process environment to read; ``None`` reads the
            process's own.
        interpreter_prefix: The running interpreter's prefix; ``None`` reads
            :data:`sys.prefix`.

    Returns:
        Whether a key is configured, and from which source.
    """
    credential = resolve_credential(
        VAULTSPEC_CORE_TYPESAFE_API_KEY,
        root,
        environ,
        interpreter_prefix=interpreter_prefix,
    )
    if credential is None:
        return HostedSearchConfig(configured=False)
    return HostedSearchConfig(configured=True, source=credential.source)


@dataclass(frozen=True)
class DiscoveryCapability:
    """What vault discovery a workspace is configured for. Never the key.

    Attributes:
        hosted_search: Whether hosted search has a credential, and from where.
        companion: The semantic-search companion's provisioning, or ``None``
            when the probe itself failed.
    """

    hosted_search: HostedSearchConfig
    companion: CompanionCapability | None


def discovery_capability(root: Path) -> DiscoveryCapability:
    """Read which vault discovery *root* is configured for.

    Args:
        root: The workspace root.

    Returns:
        The hosted-search configuration and the companion's provisioning.
    """
    from ..core.diagnosis.collectors_companion import probe_companion

    return DiscoveryCapability(
        hosted_search=hosted_search_config(root), companion=probe_companion(root)
    )


def discovery_fields(capability: DiscoveryCapability) -> dict[str, object]:
    """Project *capability* onto the keys every ``status`` surface carries.

    Args:
        capability: The capability :func:`discovery_capability` read.

    Returns:
        ``hosted_search`` and ``companion``, each as its dataclass's fields.
        ``companion`` is absent when the probe failed, never null, so the CLI
        and the MCP result, whose schema publishes no null, send the same
        keys.
    """
    fields: dict[str, object] = {
        "hosted_search": dataclasses.asdict(capability.hosted_search)
    }
    if capability.companion is not None:
        fields["companion"] = dataclasses.asdict(capability.companion)
    return fields
