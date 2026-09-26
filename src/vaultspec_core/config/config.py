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
through :func:`env_value` and :func:`env_flag`, and child processes get their
environment from :func:`child_environment`. All take registry entries, never
names.

Another vaultspec package declares its own entries through
:func:`register_registry` and then uses the same accessors, so the resolution
order lives here once rather than once per package. A package-scoped entry may
chain to a framework-scoped one through its ``fallback``: the package's own
name is read first, and the shared name behind it supplies the value when it
does not.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ..core.enums import DirName
from ..core.exceptions import ConfigurationError
from ..env_values import BOOL_SHAPE, is_blank, parse_bool, rejection

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


__all__ = [
    "CI",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "COLUMNS",
    "CONFIG_REGISTRY",
    "EDITOR",
    "GIT_INDEX_FILE",
    "NO_COLOR",
    "PACKAGE",
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
    "env_flag",
    "env_present",
    "env_source",
    "env_value",
    "get_config",
    "parse_csv_list",
    "parse_float_or_none",
    "parse_int_or_none",
    "register_registry",
    "reset_config",
]

#: The package whose registry this module declares.
PACKAGE: Final = "vaultspec-core"


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
        environ: Mapping[str, str] | None = None,
    ) -> VaultSpecConfig:
        """Create a config from environment variables and optional overrides.

        Resolution order per attribute:

        1. *overrides* dict (keyed by ``attr_name``)
        2. ``VAULTSPEC_*`` env var, blank counting as unset
        3. Dataclass default

        A value that cannot be used does not fall back to the default: a
        mistyped setting that silently does nothing is the failure this
        refusal exists to end. Every problem is collected first, so one run
        reports all of them rather than one per attempt.

        Args:
            overrides: Optional mapping of attribute name to value that takes
                precedence over environment variables and defaults.
            environ: The environment to read; ``None`` reads the process's
                own.

        Returns:
            A fully-populated ``VaultSpecConfig`` instance.

        Raises:
            ConfigurationError: If any variable carries a value the field
                cannot take, or a required one supplies nothing.
        """
        overrides = overrides or {}
        env = os.environ if environ is None else environ
        kwargs: dict[str, Any] = {}
        problems: list[str] = []

        for var in CONFIG_REGISTRY:
            # Variables read at call time are not configuration fields.
            if var.attr_name is None:
                continue

            if var.attr_name in overrides:
                kwargs[var.attr_name] = overrides[var.attr_name]
                continue

            raw = env.get(var.env_name)
            if is_blank(raw):
                if var.required:
                    problems.append(
                        f"{var.env_name} is required and no value was supplied"
                    )
                continue

            value, problem = _parse_field(var, str(raw).strip())
            if problem is not None:
                problems.append(problem)
                continue
            kwargs[var.attr_name] = value

        if problems:
            raise ConfigurationError(_collected(problems))
        return cls(**kwargs)


# Type sentinels for Optional[int] / Optional[float]  - we cannot use
# ``int | None`` as a registry *value* because the registry needs a single
# type token to drive parsing.


class _OptionalInt:
    """Sentinel type for registry entries that parse to ``int | None``."""


class _OptionalFloat:
    """Sentinel type for registry entries that parse to ``float | None``."""


def _require_bool(raw: str) -> bool:
    """Return the boolean *raw* denotes, refusing a word outside the table."""
    parsed = parse_bool(raw)
    if parsed is None:
        raise ValueError(BOOL_SHAPE)
    return parsed


# Maps a registry ``var_type`` to its ``(converter, shape)`` pair. The shape
# is what a rejection message names as the accepted form, and it is also the
# marker for the types (``bool``, ``Path``, ``list``) that carry no options
# or range constraints. Types absent from this table (``str`` /
# ``Optional[str]``) need no conversion at all.
_TYPE_CONVERTERS: dict[type, tuple[Any, str]] = {
    bool: (_require_bool, BOOL_SHAPE),
    int: (int, "a whole number"),
    float: (float, "a number"),
    Path: (Path, "a path"),
    list: (parse_csv_list, "a comma-separated list"),
    _OptionalInt: (parse_int_or_none, "a whole number"),
    _OptionalFloat: (parse_float_or_none, "a number"),
}


def _refused(var: ConfigVariable, shape: str, value: object) -> str:
    """Render one problem, withholding the value when *var* is a secret.

    A rejected secret is still a secret: the line that says a credential is
    malformed must not be the line that leaks it.
    """
    return str(rejection(var.env_name, shape, value, secret=var.secret))


def _constraint_problem(var: ConfigVariable, value: Any) -> str | None:
    """Return why *value* fails *var*'s options or range, or ``None``."""
    if var.options is not None and value not in var.options:
        return _refused(var, "one of " + ", ".join(var.options), value)
    if not isinstance(value, (int, float)):
        return None
    if var.min_value is not None and value < var.min_value:
        return _refused(var, f"at least {var.min_value}", value)
    if var.max_value is not None and value > var.max_value:
        return _refused(var, f"at most {var.max_value}", value)
    return None


def _parse_field(var: ConfigVariable, raw: str) -> tuple[Any, str | None]:
    """Parse *raw* into the type *var* declares, or say why it cannot be.

    Args:
        var: The entry describing the expected type and its constraints.
        raw: The value read from the environment, already stripped and known
            to be non-blank.

    Returns:
        The parsed value paired with ``None``, or ``None`` paired with the
        one-line problem to report. Exactly one of the two is meaningful.
    """
    converter_entry = _TYPE_CONVERTERS.get(var.var_type)
    if converter_entry is None:
        # str or Optional[str]  - no conversion needed
        return raw, _constraint_problem(var, raw)

    converter, shape = converter_entry
    try:
        value = converter(raw)
    except (ValueError, TypeError):
        # A converter's own message quotes the input verbatim, so it is the
        # declared shape that is reported, never the exception's text.
        return None, _refused(var, shape, raw)

    # The optional converters answer None rather than raising.
    if value is None:
        return None, _refused(var, shape, raw)
    return value, _constraint_problem(var, value)


def _collected(problems: list[str]) -> str:
    """Render every problem as one message, so one run reports them all."""
    if len(problems) == 1:
        return problems[0]
    listed = "\n".join(f"  - {problem}" for problem in problems)
    return f"{len(problems)} unusable settings:\n{listed}"


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
            the value when the workspace runs the owning package from its own
            environment (see :mod:`vaultspec_core.config.credential`). Only a
            secret may be so marked: the file is repository content, and it
            supplies credentials, never settings.
        fallback: The framework-scoped entry this one chains to. A
            package-scoped name is read first; when it supplies nothing, the
            shared name behind it is read. A credential never chains, and an
            external convention is not the framework's to chain.
        package: Which package declared the entry. Set by
            :func:`register_registry`, never by the caller that builds it.

    Raises:
        ValueError: If the name's prefix does not match the scope, a
            non-secret variable is marked ``workspace_dotenv``, or a
            credential or external convention declares a fallback.
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
    fallback: ConfigVariable | None = None
    package: str | None = field(default=None, init=False)

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
        if self.fallback is None:
            return
        # A credential is enrolled by one name, so that a key provisioned for
        # one package never reaches another. Chaining would give it a second.
        if self.secret or self.fallback.secret:
            raise ValueError(f"{self.env_name}: a credential never chains")
        if self.scope is VariableScope.EXTERNAL:
            raise ValueError(
                f"{self.env_name}: an external convention declares no fallback"
            )


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
        "after the --editor flag and the project config key, before VISUAL "
        "and EDITOR."
    ),
)

VAULTSPEC_CORE_TYPESAFE_API_KEY: Final = ConfigVariable(
    env_name="VAULTSPEC_CORE_TYPESAFE_API_KEY",
    attr_name="typesafe_api_key",
    var_type=str,
    default=None,
    description=(
        "TypeSafe API key that enables hosted vault search. Read from the "
        "process environment first. A workspace-root .env supplies it only "
        "when vaultspec-core runs from the workspace's own environment (its "
        "project virtual environment) in dependency or dev mode, never for "
        "a globally installed tool. Unset or blank means hosted search is "
        "not configured."
    ),
    secret=True,
    workspace_dotenv=True,
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
    description=(
        "Indents --json output. A true word turns it on; unset, blank or a "
        "false word leaves the envelope one compact line."
    ),
)

VAULTSPEC_NO_HINTS: Final = ConfigVariable(
    env_name="VAULTSPEC_NO_HINTS",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set to a true word to drop the Next actions block commands print "
        "after their report; equivalent to --no-hints. Unset, blank or a "
        "false word leaves the hints in place."
    ),
)

VAULTSPEC_NON_INTERACTIVE: Final = ConfigVariable(
    env_name="VAULTSPEC_NON_INTERACTIVE",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set to a true word to declare that no operator is watching: "
        "repository triggers awaiting approval are skipped instead of "
        "prompted for. Unset, blank or a false word leaves the terminal and "
        "CI to decide."
    ),
)

VAULTSPEC_STDIO_WATCHDOG: Final = ConfigVariable(
    env_name="VAULTSPEC_STDIO_WATCHDOG",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Lifetime watchdog of the MCP server, on by default. A false word "
        "disables it, leaving stdin EOF as the only exit path. Unset, blank "
        "or an unrecognised word leaves it armed: it is a protective switch, "
        "so a typo warns rather than turning the guard off."
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

GIT_INDEX_FILE: Final = ConfigVariable(
    env_name="GIT_INDEX_FILE",
    attr_name=None,
    var_type=str,
    default=None,
    description=(
        "Set by git for every commit hook it runs. Next-step hints and "
        "auto-fix suggestions are suppressed while it is set, because hook "
        "output is often acted on without review."
    ),
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
        attr_name="io_buffer_size",
        var_type=int,
        default=8192,
        description="I/O read buffer size in bytes.",
        min_value=1,
    ),
    ConfigVariable(
        env_name="VAULTSPEC_TERMINAL_OUTPUT_LIMIT",
        attr_name="terminal_output_limit",
        var_type=int,
        default=1_000_000,
        description="Terminal output byte limit for subprocess capture.",
        min_value=1,
    ),
    # -- Concurrency -----------------------------------------------------------
    ConfigVariable(
        env_name="VAULTSPEC_LOCK_TIMEOUT_SECONDS",
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
    GIT_INDEX_FILE,
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


#: Which package declared each registered entry, keyed by the entry's
#: identity, so the accessors below refuse a variable that was built somewhere
#: else instead of declared in a registry.
_DECLARED_BY: Final[dict[int, str]] = {}

#: The registries themselves, which also keep every registered entry alive:
#: identities are only unique while the objects behind them are.
_REGISTRIES: Final[dict[str, list[ConfigVariable]]] = {}


def register_registry(package: str, entries: Iterable[ConfigVariable]) -> None:
    """Declare *package*'s environment variables, opening the accessors to them.

    A package that wants :func:`env_value`, :func:`env_flag`,
    :func:`child_environment` and
    :func:`~vaultspec_core.config.credential.resolve_credential` for its own
    variables registers them once, at import. Registration is what binds an
    entry to the package whose install mode gates its credentials, so an
    entry belongs to exactly one package.

    Args:
        package: The distribution name declaring the entries.
        entries: The entries to register. Registering the same entries again
            under the same package is a no-op.

    Raises:
        ValueError: If an entry is already registered by another package, or
            chains to an entry no registry declares.
    """
    declared = list(entries)
    for var in declared:
        owner = _DECLARED_BY.get(id(var))
        if owner is not None and owner != package:
            raise ValueError(
                f"{var.env_name} is already declared by {owner}; "
                f"an entry belongs to one package"
            )
    known = _DECLARED_BY.keys() | {id(var) for var in declared}
    for var in declared:
        if var.fallback is not None and id(var.fallback) not in known:
            raise ValueError(
                f"{var.env_name} falls back to {var.fallback.env_name}, "
                f"which no registry declares"
            )

    registry = _REGISTRIES.setdefault(package, [])
    for var in declared:
        if id(var) in _DECLARED_BY:
            continue
        var.package = package
        _DECLARED_BY[id(var)] = package
        registry.append(var)


register_registry(PACKAGE, CONFIG_REGISTRY)


def _registered(var: ConfigVariable) -> ConfigVariable:
    """Return *var*, refusing one that no registry declares."""
    if id(var) not in _DECLARED_BY:
        raise ValueError(f"{var.env_name} is not declared in a registry")
    return var


def _supplied(
    var: ConfigVariable, environ: Mapping[str, str] | None
) -> tuple[ConfigVariable, str] | None:
    """Return the entry along *var*'s chain that supplies a value, and it.

    Args:
        var: A registered entry, possibly chaining to a framework entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        The supplying entry and its value, stripped, or ``None`` when no rung
        of the chain is set to anything but blank.

    Raises:
        ValueError: If *var* is not a registered entry.
    """
    env = os.environ if environ is None else environ
    entry: ConfigVariable | None = _registered(var)
    while entry is not None:
        raw = env.get(entry.env_name)
        if not is_blank(raw):
            # is_blank has already ruled None out.
            return entry, str(raw).strip()
        entry = entry.fallback
    return None


def env_value(
    var: ConfigVariable, environ: Mapping[str, str] | None = None
) -> str | None:
    """Return the value of registered variable *var*, read now.

    For variables whose meaning is decided where they are used, and which
    must track the environment at call time rather than when the
    configuration loaded. A blank value is unset: it falls through to the
    entry's framework fallback, and then reads as nothing at all, so a
    variable cleared in a shell profile means the same as one never set.

    Args:
        var: A registered entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        The value, stripped of surrounding whitespace, from the first rung of
        the chain that supplies one; ``None`` when none does.

    Raises:
        ValueError: If *var* is not a registered entry.
    """
    supplied = _supplied(var, environ)
    return None if supplied is None else supplied[1]


def env_source(
    var: ConfigVariable, environ: Mapping[str, str] | None = None
) -> ConfigVariable | None:
    """Return which entry along *var*'s chain supplied its value.

    A message about an unusable value must name the variable the operator
    actually set, which is *var* itself or the framework entry behind it.

    Args:
        var: A registered entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        The supplying entry, or ``None`` when the chain supplies nothing.

    Raises:
        ValueError: If *var* is not a registered entry.
    """
    supplied = _supplied(var, environ)
    return None if supplied is None else supplied[0]


def env_present(var: ConfigVariable, environ: Mapping[str, str] | None = None) -> bool:
    """Return whether *var* is set at all, blank included.

    For the external conventions whose owners define them by presence -
    ``CI``, ``NO_COLOR``, ``GIT_INDEX_FILE`` - which keep their owners'
    meanings rather than the product's blank-is-unset rule. A product-owned
    switch is read with :func:`env_flag` instead.

    Args:
        var: A registered entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        ``True`` when the environment sets the name, whatever its value.

    Raises:
        ValueError: If *var* is not a registered entry.
    """
    env = os.environ if environ is None else environ
    return _registered(var).env_name in env


def env_flag(
    var: ConfigVariable, environ: Mapping[str, str] | None = None
) -> bool | None:
    """Return the switch *var* carries, in the one boolean vocabulary.

    Args:
        var: A registered entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        ``True`` or ``False`` from the first rung of the chain that supplies a
        value; ``None`` when none does, leaving the default to the caller.

    Raises:
        ValueError: If *var* is not a registered entry.
        ConfigurationError: If a rung supplies a word the vocabulary does not
            recognise.
    """
    supplied = _supplied(var, environ)
    if supplied is None:
        return None
    entry, raw = supplied
    parsed = parse_bool(raw)
    if parsed is None:
        raise ConfigurationError(
            str(rejection(entry.env_name, BOOL_SHAPE, raw, secret=entry.secret))
        )
    return parsed


def child_environment(*assignments: tuple[ConfigVariable, str]) -> dict[str, str]:
    """Build a child process's environment: this one's, plus *assignments*.

    Assignments are applied after the copy, so an inherited value never
    overrides one set here.

    Args:
        *assignments: ``(variable, value)`` pairs of registry entries to set.

    Returns:
        A fresh mapping the caller may hand to :mod:`subprocess`.

    Raises:
        ValueError: If a variable is not a registered entry.
    """
    env = dict(os.environ)
    for var, value in assignments:
        env[_registered(var).env_name] = value
    return env


_cached_config: VaultSpecConfig | None = None
_config_lock = threading.Lock()


def get_config(overrides: dict[str, Any] | None = None) -> VaultSpecConfig:
    """Return the global ``VaultSpecConfig`` instance.

    If *overrides* is provided a fresh instance is created (not cached).
    Otherwise the cached singleton is returned, creating it on first call.
    Thread-safe: concurrent callers from the MCP server will not race
    on the read-modify of ``_cached_config``.

    Args:
        overrides: Optional attribute overrides passed directly to
            :meth:`VaultSpecConfig.from_environment`. When provided, the
            result is not cached.

    Returns:
        The current (or freshly created) ``VaultSpecConfig`` singleton.
    """
    global _cached_config

    if overrides is not None:
        return VaultSpecConfig.from_environment(overrides)

    with _config_lock:
        if _cached_config is None:
            _cached_config = VaultSpecConfig.from_environment()
        return _cached_config


def reset_config() -> None:
    """Clear the cached singleton so the next :func:`get_config` recreates it."""
    global _cached_config
    with _config_lock:
        _cached_config = None
