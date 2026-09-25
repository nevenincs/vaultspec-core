"""Runtime configuration model and singleton access for vaultspec.

Centralizes typed defaults, ``VAULTSPEC_*`` env-var parsing, and the
:func:`get_config` singleton pattern. Key exports: :class:`VaultSpecConfig`,
:class:`ConfigVariable`, :data:`CONFIG_REGISTRY`, :func:`get_config`,
:func:`reset_config`, and three parse helpers. Consumed by every module
that reads workspace settings; re-exported via :mod:`vaultspec_core.config`.

The registry is total: every environment variable the product reads or sets
is declared in it exactly once, including the external conventions it honours
(``CI``, ``NO_COLOR``, ``VISUAL`` ...) and the internal marker it sets for its
own child processes. This module is the only place the process environment is
touched. Settings that load once become :class:`VaultSpecConfig` fields;
variables whose meaning is decided where they are used are read at call time
through :func:`env_value`, and child processes get their environment from
:func:`child_environment`. Both take registry entries, never names.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ..core.enums import DirName

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

__all__ = [
    "CI",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "COLUMNS",
    "CONFIG_REGISTRY",
    "EDITOR",
    "NO_COLOR",
    "VAULTSPEC_CORE_TYPESAFE_API_KEY",
    "VAULTSPEC_EDITOR",
    "VAULTSPEC_JSON_PRETTY",
    "VAULTSPEC_LOG_LEVEL",
    "VAULTSPEC_MCP_GATEWAY_INVOCATION",
    "VAULTSPEC_NON_INTERACTIVE",
    "VAULTSPEC_NO_HINTS",
    "VAULTSPEC_STDIO_WATCHDOG",
    "VAULTSPEC_TARGET_DIR",
    "VISUAL",
    "ConfigVariable",
    "VariableScope",
    "VaultSpecConfig",
    "child_environment",
    "env_value",
    "get_config",
    "parse_csv_list",
    "parse_float_or_none",
    "parse_int_or_none",
    "reset_config",
]


def parse_csv_list(value: str) -> list[str]:
    """Split a comma-separated string into a list of stripped, non-empty items.

    Args:
        value: Comma-separated string to split.

    Returns:
        List of non-empty, whitespace-stripped tokens.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_int_or_none(value: str | None) -> int | None:
    """Parse *value* as an ``int``, returning ``None`` on failure.

    Args:
        value: String to parse.

    Returns:
        Parsed integer, or ``None`` if the string cannot be converted.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_float_or_none(value: str | None) -> float | None:
    """Parse *value* as a ``float``, returning ``None`` on failure.

    Args:
        value: String to parse.

    Returns:
        Parsed float, or ``None`` if the string cannot be converted.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@dataclass
class VaultSpecConfig:
    """Central configuration for the vaultspec framework.

    Every configurable constant used by any module should appear here with
    its production default. Instances are normally created via
    :meth:`from_environment`, which reads env vars and applies overrides.

    Attributes:
        target_dir: The root directory for the workspace (where .vault/ and
            .vaultspec/ live).
        docs_dir: Documentation vault directory name.
        index_dir: Subdirectory of :attr:`docs_dir` that holds auto-generated
            feature index files (``<feature>.index.md``).
        framework_dir: Framework directory name.
        claude_dir: Claude tool directory name.
        gemini_dir: Gemini tool directory name.
        io_buffer_size: I/O read buffer size in bytes.
        terminal_output_limit: Terminal output byte limit for subprocess capture.
        lock_timeout_seconds: Total budget, in seconds, that a single
            :func:`~vaultspec_core.core.helpers.advisory_lock` acquisition may
            spend waiting before it reports a timeout instead of blocking on.
        editor: Default editor command for creating rules/skills.
        typesafe_api_key: The hosted vault search credential, or ``None``.
            A secret: it is excluded from ``repr`` and redacted from every
            configuration log line. Hosted search resolves it through
            :func:`~vaultspec_core.config.credential.resolve_credential`,
            which also consults the workspace ``.env`` in dependency and dev
            install modes.
    """

    # -- Root ------------------------------------------------------------------
    target_dir: Path = field(default_factory=Path.cwd)

    # -- Storage ---------------------------------------------------------------
    docs_dir: str = DirName.VAULT.value
    index_dir: str = DirName.INDEX.value
    framework_dir: str = DirName.VAULTSPEC.value

    # -- Tool directories ------------------------------------------------------
    claude_dir: str = DirName.CLAUDE.value
    gemini_dir: str = DirName.GEMINI.value
    antigravity_dir: str = DirName.ANTIGRAVITY.value

    # -- I/O -------------------------------------------------------------------
    io_buffer_size: int = 8192
    terminal_output_limit: int = 1_000_000

    # -- Concurrency -----------------------------------------------------------
    lock_timeout_seconds: float = 120.0

    # -- Editor ----------------------------------------------------------------
    editor: str = "zed -w"

    # -- Vault search ----------------------------------------------------------
    typesafe_api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(
        cls,
        overrides: dict[str, Any] | None = None,
        *,
        root: Path | None = None,
    ) -> VaultSpecConfig:
        """Create a config from environment variables and optional overrides.

        Resolution order per attribute:

        1. *overrides* dict (keyed by ``attr_name``)
        2. ``VAULTSPEC_*`` env var
        3. Explicitly provisioned project settings
        4. Dataclass default

        Args:
            overrides: Optional mapping of attribute name to value that takes
                precedence over environment variables and defaults.
            root: Workspace whose explicitly provisioned settings may be read.

        Returns:
            A fully-populated ``VaultSpecConfig`` instance.

        Raises:
            ValueError: If a required variable has no value from any source.
        """
        overrides = overrides or {}
        kwargs: dict[str, Any] = {}
        from .local_env import read_local_environment

        local = read_local_environment(_config_root(root))

        for var in CONFIG_REGISTRY:
            # Variables read at call time are not configuration fields.
            if var.attr_name is None:
                continue

            # 1. Explicit override
            if var.attr_name in overrides:
                kwargs[var.attr_name] = overrides[var.attr_name]
                continue

            # 2. VAULTSPEC_* env var
            raw: str | None = os.environ.get(var.env_name)
            if raw is None and var.persistable:
                raw = local.get(var.env_name)
            source: str | None = var.env_name if raw is not None else None

            # 3. Default
            if raw is None:
                if var.required:
                    raise ValueError(
                        f"Required config variable {var.env_name} "
                        f"(attr: {var.attr_name}) is not set and no "
                        f"override was provided."
                    )
                # Skip  - dataclass default will apply
                continue

            # Parse the raw string value into the target type
            parsed = _parse_raw(var, raw, source)
            if parsed is _SENTINEL:
                continue  # parse failed, fall back to default
            kwargs[var.attr_name] = parsed

        return cls(**kwargs)


# Sentinel for parse failures
_SENTINEL = object()


# Type sentinels for Optional[int] / Optional[float]  - we cannot use
# ``int | None`` as a registry *value* because the registry needs a single
# type token to drive parsing.


class _OptionalInt:
    """Sentinel type for registry entries that parse to ``int | None``."""


class _OptionalFloat:
    """Sentinel type for registry entries that parse to ``float | None``."""


def _parse_bool(raw: str) -> bool:
    """Parse a boolean environment variable value."""
    return raw.lower() in ("1", "true", "yes")


# Maps a registry ``var_type`` to its ``(converter, skip_validation)`` pair.
# ``skip_validation`` is ``True`` for types (``bool``, ``Path``, ``list``)
# whose values bypass the options/range validation applied to the rest.
# Types absent from this table (``str`` / ``Optional[str]``) need no
# conversion and are handled by the ``_convert_raw_value`` fallback.
_TYPE_CONVERTERS: dict[type, tuple[Any, bool]] = {
    bool: (_parse_bool, True),
    int: (int, False),
    float: (float, False),
    Path: (Path, True),
    list: (parse_csv_list, True),
    _OptionalInt: (parse_int_or_none, False),
    _OptionalFloat: (parse_float_or_none, False),
}


def _convert_raw_value(var: ConfigVariable, raw: str) -> tuple[Any, bool]:
    """Convert *raw* into the type expected by *var*.

    Args:
        var: The ``ConfigVariable`` metadata that describes the expected type.
        raw: The raw string value read from the environment variable.

    Returns:
        A ``(value, skip_validation)`` tuple. ``skip_validation`` is ``True``
        for types (``bool``, ``Path``, ``list``) whose values bypass the
        options/range validation applied to the remaining types; ``value``
        is ``None`` for ``_OptionalInt``/``_OptionalFloat`` when parsing
        failed.

    Raises:
        ValueError: Propagated from ``int()``/``float()`` on malformed input.
        TypeError: Propagated from the underlying conversion call.
    """
    converter_entry = _TYPE_CONVERTERS.get(var.var_type)
    if converter_entry is None:
        # str or Optional[str]  - no conversion needed
        return raw, False
    converter, skip_validation = converter_entry
    return converter(raw), skip_validation


#: What a log line shows in place of a secret variable's value.
_REDACTED = "<redacted>"


def _shown(var: ConfigVariable, value: object) -> str:
    """Render *value* for a log line, withholding it when *var* is secret.

    A rejected secret is still a secret: the line that says a credential was
    malformed must not be the line that leaks it.
    """
    return _REDACTED if var.secret else repr(value)


def _validate_value(var: ConfigVariable, value: Any, source: str | None) -> bool:
    """Validate an already-converted *value* against *var*'s constraints.

    Args:
        var: The ``ConfigVariable`` metadata describing the options/range
            constraints.
        value: The converted value to validate.
        source: Human-readable source label for error messages.

    Returns:
        ``True`` if *value* satisfies every configured constraint, ``False``
        otherwise (a matching error has already been logged).
    """
    if var.options is not None and value not in var.options:
        logger.error(
            "%s=%s is not one of %s (source: %s); using default",
            var.attr_name,
            _shown(var, value),
            var.options,
            source,
        )
        return False

    if (
        var.min_value is not None
        and isinstance(value, (int, float))
        and value < var.min_value
    ):
        logger.error(
            "%s=%s is below minimum %s (source: %s); using default",
            var.attr_name,
            _shown(var, value),
            var.min_value,
            source,
        )
        return False

    if (
        var.max_value is not None
        and isinstance(value, (int, float))
        and value > var.max_value
    ):
        logger.error(
            "%s=%s exceeds maximum %s (source: %s); using default",
            var.attr_name,
            _shown(var, value),
            var.max_value,
            source,
        )
        return False

    return True


def _parse_raw(var: ConfigVariable, raw: str, source: str | None) -> Any:
    """Parse a raw env-var string into the type expected by *var*.

    Args:
        var: The ``ConfigVariable`` metadata that describes the expected type
            and validation constraints.
        raw: The raw string value read from the environment variable.
        source: Human-readable source label for error messages (typically the
            env var name), or ``None``.

    Returns:
        The parsed and validated value, or ``_SENTINEL`` if parsing or
        validation fails (caller should fall back to the dataclass default).
    """
    try:
        value, skip_validation = _convert_raw_value(var, raw)
    except (ValueError, TypeError) as exc:
        # A converter's own message and traceback quote the input verbatim,
        # so a secret's failure is reported without either.
        logger.error(
            "Failed to parse %s=%s (source: %s): %s; using default",
            var.attr_name,
            _shown(var, raw),
            source,
            _REDACTED if var.secret else exc,
            exc_info=not var.secret,
        )
        return _SENTINEL

    if var.var_type in (_OptionalInt, _OptionalFloat) and value is None:
        logger.error(
            "Could not parse %s=%s as %s (source: %s); using default",
            var.attr_name,
            _shown(var, raw),
            "int" if var.var_type is _OptionalInt else "float",
            source,
        )
        return _SENTINEL

    if skip_validation or _validate_value(var, value, source):
        return value
    return _SENTINEL


class VariableScope(StrEnum):
    """Who owns an environment variable the product reads or sets.

    Attributes:
        PRODUCT: A ``VAULTSPEC_*`` setting an operator sets to configure
            vaultspec-core.
        INTERNAL: A ``VAULTSPEC_*`` marker vaultspec-core sets on its own
            child processes. Documented, but not an operator setting.
        EXTERNAL: A convention another tool or standard owns, which
            vaultspec-core honours. Not held to the ``VAULTSPEC_`` prefix.
    """

    PRODUCT = "product"
    INTERNAL = "internal"
    EXTERNAL = "external"


#: The prefix every variable vaultspec-core owns carries.
_OWNED_PREFIX: Final = "VAULTSPEC_"


@dataclass
class ConfigVariable:
    """Metadata for one environment variable the product reads or sets.

    Used by :meth:`VaultSpecConfig.from_environment` to drive env-var
    resolution, parsing, and validation, and by :func:`env_value` and
    :func:`child_environment` for variables read or set at call time.

    Attributes:
        env_name: The environment variable name; ``VAULTSPEC_*`` unless the
            scope is :attr:`VariableScope.EXTERNAL`.
        attr_name: The corresponding attribute name on ``VaultSpecConfig``,
            or ``None`` for a variable read at call time through
            :func:`env_value` rather than loaded into the configuration.
        var_type: The target Python type for parsing (e.g. ``int``, ``Path``).
        default: The default value when neither override nor env var is set.
        description: Human-readable description of the variable's purpose.
        required: If ``True``, raises ``ValueError`` when no value is found.
        options: Allowed string values; ``None`` means no restriction.
        min_value: Minimum numeric value (inclusive); ``None`` means no minimum.
        max_value: Maximum numeric value (inclusive); ``None`` means no maximum.
        secret: If ``True``, the value is a credential: every log line that
            would quote it shows a redaction marker instead, and surfaces
            report only whether it is set.
        scope: Who owns the variable; see :class:`VariableScope`.
        workspace_dotenv: If ``True``, a workspace-root ``.env`` may supply
            the value when the workspace runs core from its own environment
            (see :mod:`vaultspec_core.config.credential`). Only a secret may
            be so marked: the file is repository content, and it supplies
            credentials, never settings.
        persistable: Whether installation may import this variable into protected
            project-local storage.

    Raises:
        ValueError: If the name's prefix does not match the scope, or a
            non-secret variable is marked ``workspace_dotenv``.
    """

    env_name: str
    attr_name: str | None
    var_type: type
    default: Any
    description: str
    required: bool = False
    options: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None
    secret: bool = False
    scope: VariableScope = VariableScope.PRODUCT
    workspace_dotenv: bool = False
    persistable: bool = False

    def __post_init__(self) -> None:
        owned = self.scope is not VariableScope.EXTERNAL
        if owned != self.env_name.startswith(_OWNED_PREFIX):
            requirement = "must" if owned else "must not"
            raise ValueError(
                f"{self.env_name}: a {self.scope.value} variable {requirement} "
                f"start with {_OWNED_PREFIX}"
            )
        if self.workspace_dotenv and not self.secret:
            raise ValueError(
                f"{self.env_name}: only a secret may be read from a workspace .env"
            )
        if self.persistable and self.scope is not VariableScope.PRODUCT:
            raise ValueError(f"{self.env_name}: only product settings may be persisted")


# -- Entries call sites name -----------------------------------------------------
# Each is one registry entry, bound to a name so the code that reads or sets it
# can hand it to env_value() or child_environment(), or name it in a message.
# How a raw value is interpreted (presence, one exact token, a set of off
# values) stays with the code that uses it.

VAULTSPEC_TARGET_DIR: Final = ConfigVariable(
    env_name="VAULTSPEC_TARGET_DIR",
    attr_name="target_dir",
    var_type=Path,
    default=None,
    description="The root directory for the workspace (where .vault/ and "
    ".vaultspec/ live).",
)

VAULTSPEC_EDITOR: Final = ConfigVariable(
    env_name="VAULTSPEC_EDITOR",
    attr_name="editor",
    var_type=str,
    default="zed -w",
    description=(
        "Editor command. Interactive creation of a rule, skill, agent or "
        "trigger opens it, or zed -w when unset. The edit verbs consult it "
        "after the --editor flag, before VISUAL, EDITOR and the project config key."
    ),
)

VAULTSPEC_CORE_TYPESAFE_API_KEY: Final = ConfigVariable(
    env_name="VAULTSPEC_CORE_TYPESAFE_API_KEY",
    attr_name="typesafe_api_key",
    var_type=str,
    default=None,
    description=(
        "TypeSafe API key that enables hosted vault search. Read from the "
        "process environment first, then explicitly provisioned local settings. "
        "A workspace-root .env supplies it only "
        "when vaultspec-core runs from the workspace's own environment (its "
        "project virtual environment) in dependency or dev mode, never for "
        "a globally installed tool. A blank override disables hosted search."
    ),
    secret=True,
    workspace_dotenv=True,
    persistable=True,
)

VAULTSPEC_LOG_LEVEL: Final = ConfigVariable(
    env_name="VAULTSPEC_LOG_LEVEL",
    attr_name=None,
    var_type=str,
    default="INFO",
    description=(
        "Root log level when no --debug, --quiet or explicit level is given, "
        "for example DEBUG, INFO or WARNING. An unknown name means INFO."
    ),
)

VAULTSPEC_JSON_PRETTY: Final = ConfigVariable(
    env_name="VAULTSPEC_JSON_PRETTY",
    attr_name=None,
    var_type=str,
    default=None,
    persistable=True,
    description=(
        "Indents --json output. Any value other than 0, false, no, off or "
        "blank turns it on; unset, the envelope is one compact line."
    ),
)

VAULTSPEC_NO_HINTS: Final = ConfigVariable(
    env_name="VAULTSPEC_NO_HINTS",
    attr_name=None,
    var_type=str,
    default=None,
    persistable=True,
    description=(
        "Set to 1 to drop the Next actions block commands print after their "
        "report; equivalent to --no-hints. Only the exact value 1 counts."
    ),
)

VAULTSPEC_NON_INTERACTIVE: Final = ConfigVariable(
    env_name="VAULTSPEC_NON_INTERACTIVE",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set to any value, even blank, to declare that no operator is "
        "watching, as CI does: repository triggers awaiting approval are "
        "skipped instead of prompted for."
    ),
)

VAULTSPEC_STDIO_WATCHDOG: Final = ConfigVariable(
    env_name="VAULTSPEC_STDIO_WATCHDOG",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Lifetime watchdog of the MCP server, on by default. 0, false, off or "
        "no disables it, leaving stdin EOF as the only exit path."
    ),
)

VAULTSPEC_MCP_GATEWAY_INVOCATION: Final = ConfigVariable(
    env_name="VAULTSPEC_MCP_GATEWAY_INVOCATION",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set by the MCP invoke gateway on every CLI process it spawns. Any "
        "non-empty value marks the process as having no terminal, so it "
        "refuses to open an editor. Not an operator setting."
    ),
    scope=VariableScope.INTERNAL,
)

CI: Final = ConfigVariable(
    env_name="CI",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set to any value, even blank, by CI systems: repository triggers "
        "awaiting approval are skipped instead of prompted for."
    ),
    scope=VariableScope.EXTERNAL,
)

NO_COLOR: Final = ConfigVariable(
    env_name="NO_COLOR",
    attr_name=None,
    var_type=str,
    default=None,
    description="Set to any value, even blank, to disable colour in console output.",
    scope=VariableScope.EXTERNAL,
)

COLUMNS: Final = ConfigVariable(
    env_name="COLUMNS",
    attr_name=None,
    var_type=int,
    default=None,
    description=(
        "Console width. When set, the console library honours it; when unset, "
        "the width is queried from the terminal once at startup."
    ),
    scope=VariableScope.EXTERNAL,
)

VISUAL: Final = ConfigVariable(
    env_name="VISUAL",
    attr_name=None,
    var_type=str,
    default=None,
    description="Editor command the edit verbs consult after VAULTSPEC_EDITOR.",
    scope=VariableScope.EXTERNAL,
)

EDITOR: Final = ConfigVariable(
    env_name="EDITOR",
    attr_name=None,
    var_type=str,
    default=None,
    description="Editor command the edit verbs consult after VISUAL.",
    scope=VariableScope.EXTERNAL,
)

CLAUDE_CONFIG_DIR: Final = ConfigVariable(
    env_name="CLAUDE_CONFIG_DIR",
    attr_name=None,
    var_type=Path,
    default=None,
    description=(
        "Claude Code's configuration home, whose .claude.json holds user-scope "
        "MCP servers. Unset means the home directory."
    ),
    scope=VariableScope.EXTERNAL,
)

CODEX_HOME: Final = ConfigVariable(
    env_name="CODEX_HOME",
    attr_name=None,
    var_type=Path,
    default=None,
    description=(
        "Codex's home, whose config.toml holds user-scope MCP servers. Unset "
        "means ~/.codex."
    ),
    scope=VariableScope.EXTERNAL,
)


CONFIG_REGISTRY: list[ConfigVariable] = [
    # -- Root ------------------------------------------------------------------
    VAULTSPEC_TARGET_DIR,
    # -- Storage ---------------------------------------------------------------
    ConfigVariable(
        env_name="VAULTSPEC_DOCS_DIR",
        attr_name="docs_dir",
        var_type=str,
        default=DirName.VAULT.value,
        description="Documentation vault directory name.",
    ),
    ConfigVariable(
        env_name="VAULTSPEC_INDEX_DIR",
        attr_name="index_dir",
        var_type=str,
        default=DirName.INDEX.value,
        description=(
            "Subdirectory of docs_dir for auto-generated feature index files "
            "(<feature>.index.md)."
        ),
    ),
    ConfigVariable(
        env_name="VAULTSPEC_FRAMEWORK_DIR",
        attr_name="framework_dir",
        var_type=str,
        default=DirName.VAULTSPEC.value,
        description="Framework directory name.",
    ),
    # -- Tool directories ------------------------------------------------------
    ConfigVariable(
        env_name="VAULTSPEC_CLAUDE_DIR",
        attr_name="claude_dir",
        var_type=str,
        default=DirName.CLAUDE.value,
        description="Claude tool directory name.",
    ),
    ConfigVariable(
        env_name="VAULTSPEC_GEMINI_DIR",
        attr_name="gemini_dir",
        var_type=str,
        default=DirName.GEMINI.value,
        description="Gemini tool directory name.",
    ),
    ConfigVariable(
        env_name="VAULTSPEC_ANTIGRAVITY_DIR",
        attr_name="antigravity_dir",
        var_type=str,
        default=DirName.ANTIGRAVITY.value,
        description="Agent tool directory name.",
    ),
    # -- I/O -------------------------------------------------------------------
    ConfigVariable(
        env_name="VAULTSPEC_IO_BUFFER_SIZE",
        persistable=True,
        attr_name="io_buffer_size",
        var_type=int,
        default=8192,
        description="I/O read buffer size in bytes.",
        min_value=1,
    ),
    ConfigVariable(
        env_name="VAULTSPEC_TERMINAL_OUTPUT_LIMIT",
        persistable=True,
        attr_name="terminal_output_limit",
        var_type=int,
        default=1_000_000,
        description="Terminal output byte limit for subprocess capture.",
        min_value=1,
    ),
    # -- Concurrency -----------------------------------------------------------
    ConfigVariable(
        env_name="VAULTSPEC_LOCK_TIMEOUT_SECONDS",
        persistable=True,
        attr_name="lock_timeout_seconds",
        var_type=float,
        default=120.0,
        description=(
            "Total seconds a single advisory-lock acquisition may wait "
            "before reporting a timeout. Covers both the in-process thread "
            "layer and the cross-process OS layer combined."
        ),
        min_value=0.0,
    ),
    # -- Editor ----------------------------------------------------------------
    VAULTSPEC_EDITOR,
    VISUAL,
    EDITOR,
    # -- Vault search ----------------------------------------------------------
    VAULTSPEC_CORE_TYPESAFE_API_KEY,
    # -- CLI output ------------------------------------------------------------
    VAULTSPEC_LOG_LEVEL,
    VAULTSPEC_JSON_PRETTY,
    VAULTSPEC_NO_HINTS,
    NO_COLOR,
    COLUMNS,
    # -- Unattended runs -------------------------------------------------------
    VAULTSPEC_NON_INTERACTIVE,
    CI,
    # -- MCP server ------------------------------------------------------------
    VAULTSPEC_STDIO_WATCHDOG,
    VAULTSPEC_MCP_GATEWAY_INVOCATION,
    # -- Provider homes --------------------------------------------------------
    CLAUDE_CONFIG_DIR,
    CODEX_HOME,
]


#: Identities of the registered entries, so the accessors below refuse a
#: variable that was built somewhere else instead of declared here.
_REGISTERED: Final = frozenset(id(var) for var in CONFIG_REGISTRY)


def _registered(var: ConfigVariable) -> ConfigVariable:
    """Return *var*, refusing one that is not a :data:`CONFIG_REGISTRY` entry."""
    if id(var) not in _REGISTERED:
        raise ValueError(f"{var.env_name} is not declared in CONFIG_REGISTRY")
    return var


def env_value(
    var: ConfigVariable,
    environ: Mapping[str, str] | None = None,
    *,
    root: Path | None = None,
) -> str | None:
    """Return the raw value of registered variable *var*, read now.

    For variables whose meaning is decided where they are used - presence
    alone, one exact token, a set of off values - and which must track the
    environment at call time rather than when the configuration loaded.

    Args:
        var: A :data:`CONFIG_REGISTRY` entry.
        environ: An explicit mapping reads only that mapping. Otherwise process
            presence overrides eligible project-local settings.
        root: Workspace for local settings; defaults to the current context.

    Returns:
        The value as set, which may be blank, or ``None`` when unset.

    Raises:
        ValueError: If *var* is not a registry entry.
    """
    env = os.environ if environ is None else environ
    name = _registered(var).env_name
    if name in env or environ is not None or not var.persistable:
        return env.get(name)
    from .local_env import read_local_environment

    return read_local_environment(_config_root(root)).get(name)


def _config_root(root: Path | None) -> Path:
    if root is not None:
        return root.resolve()
    from ..core.types import get_context

    try:
        return get_context().target_dir.resolve()
    except LookupError:
        return Path.cwd().resolve()


def child_environment(*assignments: tuple[ConfigVariable, str]) -> dict[str, str]:
    """Build a child process's environment: this one's, plus *assignments*.

    Assignments are applied after the copy, so an inherited value never
    overrides one set here.

    Args:
        *assignments: ``(variable, value)`` pairs of registry entries to set.

    Returns:
        A fresh mapping the caller may hand to :mod:`subprocess`.

    Raises:
        ValueError: If a variable is not a registry entry.
    """
    env = dict(os.environ)
    for var, value in assignments:
        env[_registered(var).env_name] = value
    return env


_cached_config: VaultSpecConfig | None = None
_cached_inputs: tuple[object, ...] | None = None
_config_lock = threading.Lock()


def get_config(
    overrides: dict[str, Any] | None = None, *, root: Path | None = None
) -> VaultSpecConfig:
    """Return configuration for the current workspace and environment.

    If *overrides* is provided a fresh instance is created (not cached).
    Otherwise the cache refreshes when the workspace or effective inputs change.
    Thread-safe: concurrent callers from the MCP server will not race
    on the read-modify of ``_cached_config``.

    Args:
        overrides: Optional attribute overrides passed directly to
            :meth:`VaultSpecConfig.from_environment`. When provided, the
            result is not cached.

    Returns:
        The current (or freshly created) ``VaultSpecConfig`` singleton.
    """
    global _cached_config, _cached_inputs

    from .local_env import read_local_environment

    root = _config_root(root)

    if overrides is not None:
        return VaultSpecConfig.from_environment(overrides, root=root)

    with _config_lock:
        inputs = (
            root,
            tuple(os.environ.get(var.env_name) for var in CONFIG_REGISTRY),
            tuple(sorted(read_local_environment(root).items())),
        )
        if _cached_config is None or inputs != _cached_inputs:
            _cached_config = VaultSpecConfig.from_environment(root=root)
            _cached_inputs = inputs
        return _cached_config


def reset_config() -> None:
    """Clear the cached singleton so the next :func:`get_config` recreates it."""
    global _cached_config, _cached_inputs
    with _config_lock:
        _cached_config = None
        _cached_inputs = None
