"""Which vault discovery this workspace can run, as orientation reports it.

Two independent facts, each read from local configuration and neither a
liveness check: whether hosted search has a credential, and whether the
semantic-search companion is provisioned. ``vaultspec-core status`` reports
both through :func:`discovery_fields`; the MCP ``status`` tool carries the
same ``hosted_search`` record, while the companion reaches an agent where it
decides something, as the next step of a search that declined.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._credential import hosted_search_config

if TYPE_CHECKING:
    from pathlib import Path

    from ..core.diagnosis.collectors_companion import CompanionCapability
    from ._models import HostedSearchConfig

__all__ = ["DiscoveryCapability", "discovery_capability", "discovery_fields"]


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
        ``hosted_search`` and ``companion``, each as its dataclass's fields;
        ``companion`` is ``None`` when the probe failed.
    """
    companion = capability.companion
    return {
        "hosted_search": dataclasses.asdict(capability.hosted_search),
        "companion": None if companion is None else dataclasses.asdict(companion),
    }
