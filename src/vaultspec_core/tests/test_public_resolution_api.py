"""The public names and call signatures another package imports.

An importing package takes vaultspec-core as a floor-only runtime
dependency with no ceiling: nothing pins the exact release it runs against
beyond the floor it declares. The only thing standing between that and a
broken import is a test in core's own gate, run before core's own release,
that pins every name, parameter, kind and default the resolution contract
promises. A change to any of them - a rename, a reordered parameter, a
default that moves - fails here first.

Every name is checked three ways: it exists where it is meant to be
imported from, it appears in the defining module's own ``__all__`` where
that module declares one, and its call signature - parameter names, kinds
and defaults, in order - matches exactly. A class or dataclass is checked
by its field set instead of a call signature.

One entry, :mod:`vaultspec_core.env_values`, carries an additional promise:
a spawn worker re-imports it per worker, so it must import nothing beyond
the standard library. That is proven from a fresh subprocess, because the
interpreter running this test has already imported vaultspec-core in full.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import sys
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = [pytest.mark.unit]

_EMPTY = inspect.Parameter.empty
_POK = inspect.Parameter.POSITIONAL_OR_KEYWORD
_KW = inspect.Parameter.KEYWORD_ONLY
_VAR_POS = inspect.Parameter.VAR_POSITIONAL


class _Pinned(NamedTuple):
    """One pinned callable: where it lives, and its exact signature."""

    public_module: str
    name: str
    defining_module: str
    params: tuple[tuple[str, inspect._ParameterKind, Any], ...]


def _param(name: str, kind: inspect._ParameterKind, default: Any = _EMPTY) -> Any:
    return (name, kind, default)


_Params = tuple[tuple[str, inspect._ParameterKind, Any], ...]


def _signature_tuple(func: Callable[..., object]) -> _Params:
    return tuple(
        (p.name, p.kind, p.default) for p in inspect.signature(func).parameters.values()
    )


# ---------------------------------------------------------------------------
# The pinned callables
# ---------------------------------------------------------------------------

_ENV_VALUES_CALLABLES: tuple[_Pinned, ...] = (
    _Pinned(
        "vaultspec_core.env_values",
        "is_blank",
        "vaultspec_core.env_values",
        (_param("raw", _POK),),
    ),
    _Pinned(
        "vaultspec_core.env_values",
        "parse_bool",
        "vaultspec_core.env_values",
        (_param("raw", _POK),),
    ),
    _Pinned(
        "vaultspec_core.env_values",
        "rejection",
        "vaultspec_core.env_values",
        (
            _param("where", _POK),
            _param("shape", _POK),
            _param("value", _POK),
            _param("secret", _KW, False),
        ),
    ),
)

_CONFIG_CALLABLES: tuple[_Pinned, ...] = (
    _Pinned(
        "vaultspec_core.config",
        "register_registry",
        "vaultspec_core.config.config",
        (_param("package", _POK), _param("entries", _POK)),
    ),
    _Pinned(
        "vaultspec_core.config",
        "env_value",
        "vaultspec_core.config.config",
        (_param("var", _POK), _param("environ", _POK, None)),
    ),
    _Pinned(
        "vaultspec_core.config",
        "env_source",
        "vaultspec_core.config.config",
        (_param("var", _POK), _param("environ", _POK, None)),
    ),
    _Pinned(
        "vaultspec_core.config",
        "env_flag",
        "vaultspec_core.config.config",
        (_param("var", _POK), _param("environ", _POK, None)),
    ),
    _Pinned(
        "vaultspec_core.config",
        "env_present",
        "vaultspec_core.config.config",
        (_param("var", _POK), _param("environ", _POK, None)),
    ),
    _Pinned(
        "vaultspec_core.config",
        "child_environment",
        "vaultspec_core.config.config",
        (_param("assignments", _VAR_POS),),
    ),
    _Pinned(
        "vaultspec_core.config",
        "resolve_credential",
        "vaultspec_core.config.credential",
        (
            _param("var", _POK),
            _param("root", _POK),
            _param("environ", _POK, None),
            _param("interpreter_prefix", _KW, None),
        ),
    ),
    _Pinned(
        "vaultspec_core.config",
        "check_environment",
        "vaultspec_core.config.config",
        (
            _param("environ", _POK, None),
            _param("package", _KW, "vaultspec-core"),
        ),
    ),
    _Pinned(
        "vaultspec_core.config",
        "resolve_target",
        "vaultspec_core.config.workspace",
        (
            _param("explicit", _POK, None),
            _param("package_root", _KW, None),
            _param("environ", _KW, None),
            _param("cwd", _KW, None),
        ),
    ),
    _Pinned(
        "vaultspec_core.config",
        "is_unattended",
        "vaultspec_core.config.session",
        (
            _param("json_output", _KW, False),
            _param("environ", _KW, None),
            _param("stdin", _KW, None),
            _param("stdout", _KW, None),
        ),
    ),
    _Pinned(
        "vaultspec_core.config",
        "unattended_declared",
        "vaultspec_core.config.session",
        (_param("environ", _POK, None),),
    ),
)

_LOGGING_CALLABLES: tuple[_Pinned, ...] = (
    _Pinned(
        "vaultspec_core.logging_config",
        "resolve_log_level",
        "vaultspec_core.logging_config",
        (
            _param("debug", _KW, False),
            _param("verbose", _KW, False),
            # The default is checked separately, by identity: it is the
            # framework's own VAULTSPEC_LOG_LEVEL entry, not a copy of it.
            _param("variable", _KW, "<VAULTSPEC_LOG_LEVEL>"),
            _param("default", _KW, "WARNING"),
            _param("environ", _KW, None),
        ),
    ),
)

_INSTALL_MODE_CALLABLES: tuple[_Pinned, ...] = (
    _Pinned(
        "vaultspec_core.core.install_mode",
        "infer_upgrade_mode",
        "vaultspec_core.core.install_mode",
        (
            _param("target", _POK),
            _param("package", _POK),
            _param("launch_is_module_run", _KW),
        ),
    ),
)

_ENVELOPE_CALLABLES: tuple[_Pinned, ...] = (
    _Pinned(
        "vaultspec_core.envelope",
        "render_envelope",
        "vaultspec_core.envelope",
        (
            _param("command", _POK),
            _param("status", _POK),
            _param("data", _POK),
            _param("version", _KW, 1),
            _param("hints", _KW, None),
        ),
    ),
    _Pinned(
        "vaultspec_core.envelope",
        "render_install_envelope",
        "vaultspec_core.envelope",
        (
            _param("schema", _POK),
            _param("status", _POK),
            _param("data", _POK),
            _param("hints", _KW, None),
        ),
    ),
    _Pinned(
        "vaultspec_core.envelope",
        "render_error_envelope",
        "vaultspec_core.envelope",
        (_param("message", _POK), _param("hint", _KW, None)),
    ),
    _Pinned(
        "vaultspec_core.envelope",
        "hints_suppressed",
        "vaultspec_core.envelope",
        (_param("no_hints", _KW, False), _param("environ", _KW, None)),
    ),
)

_ALL_PINNED: tuple[_Pinned, ...] = (
    _ENV_VALUES_CALLABLES
    + _CONFIG_CALLABLES
    + _LOGGING_CALLABLES
    + _INSTALL_MODE_CALLABLES
    + _ENVELOPE_CALLABLES
)


def _import(dotted: str) -> object:
    import importlib

    return importlib.import_module(dotted)


class TestPinnedCallableSignatures:
    """Every pinned function's parameters, in order, name, kind and default."""

    @pytest.mark.parametrize(
        "pinned", _ALL_PINNED, ids=[f"{p.public_module}.{p.name}" for p in _ALL_PINNED]
    )
    def test_importable_from_its_public_module(self, pinned: _Pinned) -> None:
        module = _import(pinned.public_module)
        assert hasattr(module, pinned.name), (
            f"{pinned.name} is not importable from {pinned.public_module}"
        )

    @pytest.mark.parametrize(
        "pinned", _ALL_PINNED, ids=[f"{p.public_module}.{p.name}" for p in _ALL_PINNED]
    )
    def test_is_the_same_object_the_defining_module_declares(
        self, pinned: _Pinned
    ) -> None:
        public = getattr(_import(pinned.public_module), pinned.name)
        defining = getattr(_import(pinned.defining_module), pinned.name)
        assert public is defining, (
            f"{pinned.public_module}.{pinned.name} is not the object "
            f"{pinned.defining_module} declares"
        )

    @pytest.mark.parametrize(
        "pinned", _ALL_PINNED, ids=[f"{p.public_module}.{p.name}" for p in _ALL_PINNED]
    )
    def test_is_listed_in_the_defining_modules_all(self, pinned: _Pinned) -> None:
        defining = _import(pinned.defining_module)
        declared = getattr(defining, "__all__", None)
        if declared is None:
            pytest.skip(f"{pinned.defining_module} declares no __all__")
        assert pinned.name in declared

    @pytest.mark.parametrize(
        "pinned", _ALL_PINNED, ids=[f"{p.public_module}.{p.name}" for p in _ALL_PINNED]
    )
    def test_signature_matches_exactly(self, pinned: _Pinned) -> None:
        func = getattr(_import(pinned.public_module), pinned.name)
        actual = _signature_tuple(func)

        # The framework-level default of resolve_log_level's `variable`
        # parameter is checked by identity below, not by the placeholder
        # string in the table.
        expected = pinned.params
        if pinned.name == "resolve_log_level":
            from vaultspec_core.config import VAULTSPEC_LOG_LEVEL

            assert actual[2][2] is VAULTSPEC_LOG_LEVEL
            placeholder = ("variable", _KW, "<VAULTSPEC_LOG_LEVEL>")
            actual = (*actual[:2], placeholder, *actual[3:])

        assert actual == expected


# ---------------------------------------------------------------------------
# Classes, dataclasses and enums: checked by field or member set.
# ---------------------------------------------------------------------------


class TestConfigVariable:
    """The dataclass a package builds its own registry entries from."""

    def test_field_names_kinds_and_defaults(self) -> None:
        from vaultspec_core.config import ConfigVariable

        fields = {f.name: f for f in dataclasses.fields(ConfigVariable)}
        expected_defaults: dict[str, Any] = {
            "required": False,
            "options": None,
            "min_value": None,
            "max_value": None,
            "secret": False,
            "workspace_dotenv": False,
            "fail_safe": False,
            "fallback": None,
        }
        required = {"env_name", "attr_name", "var_type", "default", "description"}

        assert required <= fields.keys()
        for name, default in expected_defaults.items():
            assert name in fields, f"ConfigVariable lost its {name!r} field"
            assert fields[name].default == default

        # `scope` and `package` carry non-comparable-by-equality defaults
        # (an enum member, and a caller-invisible init=False field); checked
        # by presence and by the properties the contract actually needs.
        assert "scope" in fields
        assert fields["package"].init is False

    def test_scope_defaults_to_product(self) -> None:
        from vaultspec_core.config import ConfigVariable, VariableScope

        var = ConfigVariable(
            env_name="VAULTSPEC_PUBLIC_API_PROBE",
            attr_name=None,
            var_type=str,
            default=None,
            description="probe",
        )
        assert var.scope is VariableScope.PRODUCT


class TestVariableScope:
    def test_members(self) -> None:
        from vaultspec_core.config import VariableScope

        assert {member.value for member in VariableScope} == {
            "product",
            "internal",
            "external",
        }
        assert VariableScope.PRODUCT.value == "product"
        assert VariableScope.INTERNAL.value == "internal"
        assert VariableScope.EXTERNAL.value == "external"


class TestTargetSource:
    def test_members(self) -> None:
        from vaultspec_core.config import TargetSource

        assert {member.value for member in TargetSource} == {
            "invocation",
            "environment",
            "discovery",
        }


class TestResolvedTarget:
    def test_fields(self) -> None:
        from vaultspec_core.config import ResolvedTarget

        fields = {f.name: f for f in dataclasses.fields(ResolvedTarget)}
        assert set(fields) == {"path", "source", "variable"}
        assert fields["variable"].default is None


class TestConfigurationError:
    def test_is_importable_and_is_a_valuerror_shaped_domain_error(self) -> None:
        from vaultspec_core.config import ConfigurationError
        from vaultspec_core.core.exceptions import VaultSpecError

        assert issubclass(ConfigurationError, VaultSpecError)


class TestLogLevels:
    def test_the_five_levels_in_order(self) -> None:
        from vaultspec_core.logging_config import LOG_LEVELS

        assert LOG_LEVELS == ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class TestEnvValuesVocabulary:
    def test_the_word_tables_and_shape_message(self) -> None:
        from vaultspec_core.env_values import BOOL_SHAPE, FALSE_TOKENS, TRUE_TOKENS

        assert frozenset({"1", "true", "yes", "on"}) == TRUE_TOKENS
        assert frozenset({"0", "false", "no", "off"}) == FALSE_TOKENS
        assert "one of " + ", ".join(sorted(TRUE_TOKENS | FALSE_TOKENS)) == BOOL_SHAPE


# ---------------------------------------------------------------------------
# env_values: standard-library only, proven from a fresh interpreter.
# ---------------------------------------------------------------------------


class TestEnvValuesImportsNothingBeyondTheStandardLibrary:
    """A spawn worker re-imports this module per worker, so it must stay cheap.

    Run from this test's own interpreter, the check would prove nothing: the
    whole package, and everything it depends on, is already imported. A
    fresh subprocess is the only way to see what importing the module alone
    actually pulls in.
    """

    def test_only_stdlib_modules_and_itself_appear_in_sys_modules(self) -> None:
        probe = (
            "import sys\n"
            "before = set(sys.modules)\n"
            "import vaultspec_core.env_values\n"
            "new = set(sys.modules) - before\n"
            "stdlib = set(sys.stdlib_module_names)\n"
            "offenders = sorted(\n"
            "    name for name in new\n"
            "    if name.split('.')[0] not in stdlib\n"
            "    and name not in ('vaultspec_core', 'vaultspec_core.env_values')\n"
            ")\n"
            "print(','.join(offenders))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        offenders = [name for name in result.stdout.strip().split(",") if name]
        assert not offenders, (
            "vaultspec_core.env_values pulled in modules beyond the standard "
            f"library and itself: {offenders}"
        )
