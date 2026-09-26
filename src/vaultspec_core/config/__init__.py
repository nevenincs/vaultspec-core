"""Runtime configuration and workspace-layout primitives for vaultspec_core.

Re-exports :class:`VaultSpecConfig`, :func:`get_config`, :data:`CONFIG_REGISTRY`,
its named entries, :func:`register_registry` for another package's entries, the
:func:`env_value`, :func:`env_source`, :func:`env_present`, :func:`env_flag` and
:func:`child_environment` accessors, env-var parsers and the
:class:`ConfigurationError` every one of them refuses with, from
:mod:`.config`; :func:`resolve_credential`
and its types from :mod:`.credential`; :func:`read_dotenv_value` from
:mod:`.dotenv`; and :class:`WorkspaceLayout`, :class:`LayoutMode`,
:func:`resolve_target`, :class:`ResolvedTarget`, :class:`TargetSource`,
:func:`resolve_workspace`, :func:`discover_git`, and :class:`WorkspaceError`
from :mod:`.workspace`. Consumed by nearly every subpackage that needs
vault/spec paths or runtime settings.
"""

from ..core.exceptions import ConfigurationError as ConfigurationError
from .config import CI as CI
from .config import CLAUDE_CONFIG_DIR as CLAUDE_CONFIG_DIR
from .config import CODEX_HOME as CODEX_HOME
from .config import COLUMNS as COLUMNS
from .config import CONFIG_REGISTRY as CONFIG_REGISTRY
from .config import EDITOR as EDITOR
from .config import GIT_INDEX_FILE as GIT_INDEX_FILE
from .config import NO_COLOR as NO_COLOR
from .config import PACKAGE as PACKAGE
from .config import (
    VAULTSPEC_CORE_TYPESAFE_API_KEY as VAULTSPEC_CORE_TYPESAFE_API_KEY,
)
from .config import VAULTSPEC_EDITOR as VAULTSPEC_EDITOR
from .config import VAULTSPEC_JSON_PRETTY as VAULTSPEC_JSON_PRETTY
from .config import VAULTSPEC_LOG_LEVEL as VAULTSPEC_LOG_LEVEL
from .config import (
    VAULTSPEC_MCP_GATEWAY_INVOCATION as VAULTSPEC_MCP_GATEWAY_INVOCATION,
)
from .config import VAULTSPEC_NO_HINTS as VAULTSPEC_NO_HINTS
from .config import VAULTSPEC_NON_INTERACTIVE as VAULTSPEC_NON_INTERACTIVE
from .config import VAULTSPEC_STDIO_WATCHDOG as VAULTSPEC_STDIO_WATCHDOG
from .config import VAULTSPEC_TARGET_DIR as VAULTSPEC_TARGET_DIR
from .config import VISUAL as VISUAL
from .config import ConfigVariable as ConfigVariable
from .config import VariableScope as VariableScope
from .config import VaultSpecConfig as VaultSpecConfig
from .config import check_environment as check_environment
from .config import child_environment as child_environment
from .config import env_flag as env_flag
from .config import env_present as env_present
from .config import env_source as env_source
from .config import env_value as env_value
from .config import get_config as get_config
from .config import parse_csv_list as parse_csv_list
from .config import parse_float_or_none as parse_float_or_none
from .config import parse_int_or_none as parse_int_or_none
from .config import register_registry as register_registry
from .config import reset_config as reset_config
from .credential import Credential as Credential
from .credential import CredentialSource as CredentialSource
from .credential import HostedSearchConfig as HostedSearchConfig
from .credential import resolve_credential as resolve_credential
from .dotenv import read_dotenv_value as read_dotenv_value
from .workspace import GitInfo as GitInfo
from .workspace import LayoutMode as LayoutMode
from .workspace import ResolvedTarget as ResolvedTarget
from .workspace import TargetSource as TargetSource
from .workspace import WorkspaceError as WorkspaceError
from .workspace import WorkspaceLayout as WorkspaceLayout
from .workspace import discover_git as discover_git
from .workspace import resolve_target as resolve_target
from .workspace import resolve_workspace as resolve_workspace
