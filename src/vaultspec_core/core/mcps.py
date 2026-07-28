"""Manage canonical MCP definitions and provider-native enrollment.

Definitions in ``.vaultspec/mcps/*.json`` describe provider-neutral stdio
servers. This module renders those definitions for each MCP-capable provider,
reconciles project or explicit broader-scope targets, and records ownership
outside host configuration so unrelated entries remain untouched.

A managed entry that drifted from its rendered definition converges
automatically, without ``--force``, whenever its on-disk bytes still match
the fingerprint recorded at the last write: the drift is provably one the
entry never survived a hand edit through, so refreshing it cannot destroy
user content. An entry whose bytes no longer match its recorded fingerprint,
or whose ownership record predates fingerprinting, keeps the existing
skip-and-warn behavior and still requires ``--force``.

This module is the public surface for the ``core.mcps*`` package: the
implementation is split across sibling modules by concern - mode rendering
(:mod:`~vaultspec_core.core.mcps_mode`), native-host target resolution
(:mod:`~vaultspec_core.core.mcps_targets`), ownership bookkeeping
(:mod:`~vaultspec_core.core.mcps_ownership`), native config parsing/rendering
(:mod:`~vaultspec_core.core.mcps_native`), definition collection and CRUD
(:mod:`~vaultspec_core.core.mcps_definitions`), reconciliation
(:mod:`~vaultspec_core.core.mcps_sync`), and removal
(:mod:`~vaultspec_core.core.mcps_uninstall`) - and re-exported here so every
existing import site keeps working unchanged.
"""

from __future__ import annotations

from .mcps_definitions import (
    _server_name as _server_name,
)
from .mcps_definitions import (
    collect_mcp_servers as collect_mcp_servers,
)
from .mcps_definitions import (
    mcp_add as mcp_add,
)
from .mcps_definitions import (
    mcp_list as mcp_list,
)
from .mcps_definitions import (
    mcp_remove as mcp_remove,
)
from .mcps_definitions import (
    mcp_status as mcp_status,
)
from .mcps_mode import (
    _DEFAULT_MCP_MODULE as _DEFAULT_MCP_MODULE,
)
from .mcps_mode import (
    _DEFAULT_MCP_PACKAGE as _DEFAULT_MCP_PACKAGE,
)
from .mcps_mode import (
    _MODE_ARGS_TOKEN as _MODE_ARGS_TOKEN,
)
from .mcps_mode import (
    _MODE_COMMAND_TOKEN as _MODE_COMMAND_TOKEN,
)
from .mcps_mode import (
    _MODE_MCP_LAUNCH as _MODE_MCP_LAUNCH,
)
from .mcps_mode import (
    _MODE_MODULE_KEY as _MODE_MODULE_KEY,
)
from .mcps_mode import (
    _MODE_PACKAGE_KEY as _MODE_PACKAGE_KEY,
)
from .mcps_mode import (
    _MODE_TOOL_SPEC_KEY as _MODE_TOOL_SPEC_KEY,
)
from .mcps_mode import (
    _render_definition_for_sync as _render_definition_for_sync,
)
from .mcps_mode import (
    render_launch_for_mode as render_launch_for_mode,
)
from .mcps_mode import (
    render_mcp_definition_for_mode as render_mcp_definition_for_mode,
)
from .mcps_ownership import (
    _OWNERSHIP_FILENAME as _OWNERSHIP_FILENAME,
)
from .mcps_ownership import (
    _OWNERSHIP_VERSION as _OWNERSHIP_VERSION,
)
from .mcps_ownership import (
    _ownership_path as _ownership_path,
)
from .mcps_ownership import (
    _ownership_target_key as _ownership_target_key,
)
from .mcps_ownership import (
    _read_ownership as _read_ownership,
)
from .mcps_ownership import (
    _write_ownership as _write_ownership,
)
from .mcps_ownership import (
    ownership_path as ownership_path,
)
from .mcps_ownership import (
    read_ownership as read_ownership,
)
from .mcps_sync import mcp_sync as mcp_sync
from .mcps_targets import resolve_mcp_targets as resolve_mcp_targets
from .mcps_uninstall import mcp_uninstall as mcp_uninstall
