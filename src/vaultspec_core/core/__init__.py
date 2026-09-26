"""Public surface for vaultspec resource management and sync orchestration.

Aggregates per-resource CRUD (:func:`agents_add`, :func:`rules_sync`,
:func:`skills_list`, :func:`system_sync`), the sync engine
(:func:`sync_files`), config generation
(:func:`config_show`, :func:`config_sync`), I/O helpers
(:func:`atomic_write`, :func:`build_file`), domain exceptions
(:class:`VaultSpecError` and subclasses), and path/type contracts
(:class:`SyncResult`, :class:`ToolConfig`, :class:`WorkspaceContext`).
Consumed by :mod:`vaultspec_core.cli` and :mod:`vaultspec_core.mcp_server`.

The aggregation is lazy. Python imports a package before any module inside
it, so eagerly re-exporting every name here made ``from
vaultspec_core.core.exceptions import ConfigurationError`` - one exception
class, imported by the configuration layer that every process loads first -
pull in the agent collector, the YAML parser and the whole sync engine
behind it. Each name below is resolved on first attribute access instead,
through the module ``__getattr__`` of PEP 562, and cached in this module's
namespace thereafter. Importers see no difference: ``from
vaultspec_core.core import agents_add`` still works, and still imports
exactly what it needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    # The lazy map below is invisible to a type checker, so the same names
    # are declared here in the form it does read. The two must agree: a name
    # in one and not the other is either an unresolvable import or a
    # runtime AttributeError.
    from .agents import agents_add as agents_add
    from .agents import agents_list as agents_list
    from .agents import agents_sync as agents_sync
    from .agents import collect_agents as collect_agents
    from .agents import transform_agent as transform_agent
    from .config_gen import config_show as config_show
    from .config_gen import config_sync as config_sync
    from .editor import EDITOR_PROGRAM_ALLOWLIST as EDITOR_PROGRAM_ALLOWLIST
    from .editor import EditorValidationError as EditorValidationError
    from .editor import validate_editor_command as validate_editor_command
    from .enums import InstallMode as InstallMode
    from .enums import McpScope as McpScope
    from .enums import McpTargetFormat as McpTargetFormat
    from .enums import Tool as Tool
    from .exceptions import EditorCancellationError as EditorCancellationError
    from .exceptions import EditorResolutionError as EditorResolutionError
    from .exceptions import EditorSubprocessError as EditorSubprocessError
    from .exceptions import ProviderError as ProviderError
    from .exceptions import ProviderNotInstalledError as ProviderNotInstalledError
    from .exceptions import ResourceExistsError as ResourceExistsError
    from .exceptions import ResourceNotFoundError as ResourceNotFoundError
    from .exceptions import VaultSpecError as VaultSpecError
    from .exceptions import WorkspaceNotInitializedError as WorkspaceNotInitializedError
    from .helpers import atomic_write as atomic_write
    from .helpers import build_file as build_file
    from .helpers import dump_yaml as dump_yaml
    from .helpers import ensure_dir as ensure_dir
    from .home import CoreHomeLayout as CoreHomeLayout
    from .home import ProcessRegistryDiagnosis as ProcessRegistryDiagnosis
    from .home import ProcessRegistrySignal as ProcessRegistrySignal
    from .home import core_home_layout as core_home_layout
    from .home import diagnose_process_registry as diagnose_process_registry
    from .local_config import KNOWN_KEYS as KNOWN_KEYS
    from .local_config import get_config_value as get_config_value
    from .local_config import get_local_config_path as get_local_config_path
    from .local_config import read_local_config as read_local_config
    from .local_config import resolve_editor as resolve_editor
    from .local_config import set_config_value as set_config_value
    from .local_config import unset_config_value as unset_config_value
    from .local_config import write_local_config as write_local_config
    from .mcps import collect_mcp_servers as collect_mcp_servers
    from .mcps import mcp_add as mcp_add
    from .mcps import mcp_list as mcp_list
    from .mcps import mcp_remove as mcp_remove
    from .mcps import mcp_status as mcp_status
    from .mcps import mcp_sync as mcp_sync
    from .mcps import mcp_uninstall as mcp_uninstall
    from .mcps import render_launch_for_mode as render_launch_for_mode
    from .mcps import render_mcp_definition_for_mode as render_mcp_definition_for_mode
    from .mcps import resolve_mcp_targets as resolve_mcp_targets
    from .resources import resource_edit as resource_edit
    from .resources import resource_remove as resource_remove
    from .resources import resource_rename as resource_rename
    from .resources import resource_show as resource_show
    from .rules import collect_rules as collect_rules
    from .rules import rules_add as rules_add
    from .rules import rules_list as rules_list
    from .rules import rules_sync as rules_sync
    from .rules import transform_rule as transform_rule
    from .skills import collect_skills as collect_skills
    from .skills import skills_add as skills_add
    from .skills import skills_list as skills_list
    from .skills import skills_sync as skills_sync
    from .skills import transform_skill as transform_skill
    from .sync import sync_files as sync_files
    from .system import system_show as system_show
    from .system import system_sync as system_sync
    from .triggers import triggers_add as triggers_add
    from .triggers import triggers_edit as triggers_edit
    from .triggers import triggers_remove as triggers_remove
    from .triggers import triggers_rename as triggers_rename
    from .triggers import triggers_show as triggers_show
    from .triggers import triggers_status as triggers_status
    from .types import CONFIG_HEADER as CONFIG_HEADER
    from .types import McpTarget as McpTarget
    from .types import SyncResult as SyncResult
    from .types import ToolConfig as ToolConfig
    from .types import WorkspaceContext as WorkspaceContext
    from .types import get_context as get_context
    from .types import init_paths as init_paths
    from .types import set_context as set_context

#: Every re-exported name, mapped to the submodule that defines it.
_EXPORTS: Final[dict[str, str]] = {
    "CONFIG_HEADER": "types",
    "CoreHomeLayout": "home",
    "EDITOR_PROGRAM_ALLOWLIST": "editor",
    "EditorCancellationError": "exceptions",
    "EditorResolutionError": "exceptions",
    "EditorSubprocessError": "exceptions",
    "EditorValidationError": "editor",
    "InstallMode": "enums",
    "KNOWN_KEYS": "local_config",
    "McpScope": "enums",
    "McpTarget": "types",
    "McpTargetFormat": "enums",
    "ProcessRegistryDiagnosis": "home",
    "ProcessRegistrySignal": "home",
    "ProviderError": "exceptions",
    "ProviderNotInstalledError": "exceptions",
    "ResourceExistsError": "exceptions",
    "ResourceNotFoundError": "exceptions",
    "SyncResult": "types",
    "Tool": "enums",
    "ToolConfig": "types",
    "VaultSpecError": "exceptions",
    "WorkspaceContext": "types",
    "WorkspaceNotInitializedError": "exceptions",
    "agents_add": "agents",
    "agents_list": "agents",
    "agents_sync": "agents",
    "atomic_write": "helpers",
    "build_file": "helpers",
    "collect_agents": "agents",
    "collect_mcp_servers": "mcps",
    "collect_rules": "rules",
    "collect_skills": "skills",
    "config_show": "config_gen",
    "config_sync": "config_gen",
    "core_home_layout": "home",
    "diagnose_process_registry": "home",
    "dump_yaml": "helpers",
    "ensure_dir": "helpers",
    "get_config_value": "local_config",
    "get_context": "types",
    "get_local_config_path": "local_config",
    "init_paths": "types",
    "mcp_add": "mcps",
    "mcp_list": "mcps",
    "mcp_remove": "mcps",
    "mcp_status": "mcps",
    "mcp_sync": "mcps",
    "mcp_uninstall": "mcps",
    "read_local_config": "local_config",
    "render_launch_for_mode": "mcps",
    "render_mcp_definition_for_mode": "mcps",
    "resolve_editor": "local_config",
    "resolve_mcp_targets": "mcps",
    "resource_edit": "resources",
    "resource_remove": "resources",
    "resource_rename": "resources",
    "resource_show": "resources",
    "rules_add": "rules",
    "rules_list": "rules",
    "rules_sync": "rules",
    "set_config_value": "local_config",
    "set_context": "types",
    "skills_add": "skills",
    "skills_list": "skills",
    "skills_sync": "skills",
    "sync_files": "sync",
    "system_show": "system",
    "system_sync": "system",
    "transform_agent": "agents",
    "transform_rule": "rules",
    "transform_skill": "skills",
    "triggers_add": "triggers",
    "triggers_edit": "triggers",
    "triggers_remove": "triggers",
    "triggers_rename": "triggers",
    "triggers_show": "triggers",
    "triggers_status": "triggers",
    "unset_config_value": "local_config",
    "validate_editor_command": "editor",
    "write_local_config": "local_config",
}


def __getattr__(name: str) -> Any:
    """Resolve a re-exported name on first access, then cache it."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the re-exported names alongside whatever is already bound."""
    return sorted(set(globals()) | set(_EXPORTS))
