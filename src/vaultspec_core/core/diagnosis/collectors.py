"""Signal collectors for workspace and provider diagnosis.

Each collector examines a single diagnostic axis and returns the appropriate
:mod:`~vaultspec_core.core.diagnosis.signals` enum value. This module is the
public surface for every collector; the implementations live in sibling
modules split by seam and are re-exported here so no import site outside the
package needs to change:

- :mod:`.collectors_provider` - framework presence, manifest coherence,
  provider directory completeness, builtin version state.
- :mod:`.collectors_config` - provider config files, ``.mcp.json``, vault
  template annotations, ``.gitignore``/``.gitattributes`` blocks.
- :mod:`.collectors_content` - managed rule content drift, adoption
  projection drift, rename integrity.
- :mod:`.collectors_precommit` - pre-commit hook boundary and mode.
- :mod:`.collectors_mode` - install-mode coherence, version floor, stale MCP
  seed definitions.
"""

from __future__ import annotations

from .collectors_config import (
    collect_config_state,
    collect_gitattributes_state,
    collect_gitignore_state,
    collect_mcp_config_state,
    collect_vault_content_state,
)
from .collectors_content import (
    collect_content_integrity,
    collect_divergent_projections,
    collect_rename_integrity,
)
from .collectors_mode import (
    collect_mode_mismatch_state,
    collect_stale_seed_definitions,
    collect_version_floor_state,
    observed_mcp_mode,
)
from .collectors_precommit import (
    collect_precommit_state,
    observed_precommit_mode,
    precommit_hook_installed,
)
from .collectors_provider import (
    collect_builtin_version_state,
    collect_framework_presence,
    collect_manifest_coherence,
    collect_provider_dir_state,
)

__all__ = [
    "collect_builtin_version_state",
    "collect_config_state",
    "collect_content_integrity",
    "collect_divergent_projections",
    "collect_framework_presence",
    "collect_gitattributes_state",
    "collect_gitignore_state",
    "collect_manifest_coherence",
    "collect_mcp_config_state",
    "collect_mode_mismatch_state",
    "collect_precommit_state",
    "collect_provider_dir_state",
    "collect_rename_integrity",
    "collect_stale_seed_definitions",
    "collect_vault_content_state",
    "collect_version_floor_state",
    "observed_mcp_mode",
    "observed_precommit_mode",
    "precommit_hook_installed",
]
