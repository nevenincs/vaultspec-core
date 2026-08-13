"""Workspace and provider diagnostic types.

Re-exports the signal enums from :mod:`.signals`, the dataclasses from
:mod:`.diagnosis`, and the resolution engine from :mod:`..resolver` so
consumers can import directly from the package.
"""

from __future__ import annotations

from ..resolver import ResolutionPlan, ResolutionStep, resolve
from .collectors import observed_mcp_mode
from .diagnosis import (
    HomeDiagnosis,
    PackageModeDiagnosis,
    ProviderDiagnosis,
    WorkspaceDiagnosis,
    diagnose,
)
from .signals import (
    BuiltinVersionSignal,
    ConfigSignal,
    ContentSignal,
    FrameworkSignal,
    GitattributesSignal,
    GitignoreSignal,
    ManifestEntrySignal,
    ModeMismatchSignal,
    PrecommitSignal,
    ProcessRegistrySignal,
    ProviderDirSignal,
    RenameIntegritySignal,
    ResolutionAction,
    VaultContentSignal,
    VersionFloorSignal,
)

__all__ = [
    "BuiltinVersionSignal",
    "ConfigSignal",
    "ContentSignal",
    "FrameworkSignal",
    "GitattributesSignal",
    "GitignoreSignal",
    "HomeDiagnosis",
    "ManifestEntrySignal",
    "ModeMismatchSignal",
    "PackageModeDiagnosis",
    "PrecommitSignal",
    "ProcessRegistrySignal",
    "ProviderDiagnosis",
    "ProviderDirSignal",
    "RenameIntegritySignal",
    "ResolutionAction",
    "ResolutionPlan",
    "ResolutionStep",
    "VaultContentSignal",
    "VersionFloorSignal",
    "WorkspaceDiagnosis",
    "diagnose",
    "observed_mcp_mode",
    "resolve",
]
