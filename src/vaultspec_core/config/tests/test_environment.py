"""The registry is the only door to the environment, and it is total."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import (
    CI,
    CONFIG_REGISTRY,
    EDITOR,
    NO_COLOR,
    VAULTSPEC_EDITOR,
    VAULTSPEC_MCP_GATEWAY_INVOCATION,
    VAULTSPEC_NO_HINTS,
    VAULTSPEC_TARGET_DIR,
    VISUAL,
    ConfigVariable,
    VariableScope,
    VaultSpecConfig,
    child_environment,
    env_value,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _stray(
    env_name: str = "VAULTSPEC_UNDECLARED",
    scope: VariableScope = VariableScope.PRODUCT,
) -> ConfigVariable:
    """A variable built outside the registry."""
    return ConfigVariable(
        env_name=env_name,
        attr_name=None,
        var_type=str,
        default=None,
        description="Declared outside the registry.",
        scope=scope,
    )


class TestRegistryShape:
    def test_every_name_is_declared_once(self) -> None:
        counts = Counter(var.env_name for var in CONFIG_REGISTRY)

        assert [name for name, n in counts.items() if n > 1] == []

    def test_owned_variables_carry_the_prefix_and_external_ones_do_not(self) -> None:
        for var in CONFIG_REGISTRY:
            owned = var.scope is not VariableScope.EXTERNAL
            assert var.env_name.startswith("VAULTSPEC_") is owned, var.env_name

    def test_every_scope_is_represented(self) -> None:
        assert {var.scope for var in CONFIG_REGISTRY} == set(VariableScope)

    def test_the_gateway_marker_is_internal(self) -> None:
        assert VAULTSPEC_MCP_GATEWAY_INVOCATION.scope is VariableScope.INTERNAL

    @pytest.mark.parametrize("var", [CI, NO_COLOR, VISUAL, EDITOR])
    def test_honoured_conventions_are_external(self, var: ConfigVariable) -> None:
        assert var.scope is VariableScope.EXTERNAL

    @pytest.mark.parametrize(
        ("name", "scope"),
        [
            ("EDITOR_OF_MINE", VariableScope.PRODUCT),
            ("SOME_MARKER", VariableScope.INTERNAL),
            ("VAULTSPEC_BORROWED", VariableScope.EXTERNAL),
        ],
    )
    def test_a_prefix_that_contradicts_the_scope_is_refused(
        self, name: str, scope: VariableScope
    ) -> None:
        with pytest.raises(ValueError, match="start with VAULTSPEC_"):
            _stray(env_name=name, scope=scope)


class TestEditorDefault:
    def test_the_editor_has_no_shipped_default_and_no_loaded_field(self) -> None:
        # Every rung of the editor ladder is read where the editor is opened,
        # so there is nothing for the configuration to carry, and no product
        # default above the last rung the ladder itself declares.
        assert VAULTSPEC_EDITOR.default is None
        assert VAULTSPEC_EDITOR.attr_name is None
        assert not hasattr(VaultSpecConfig(), "editor")


class TestEnvValue:
    def test_reads_the_named_variable_from_the_given_environment(self) -> None:
        environ = {"VAULTSPEC_NO_HINTS": "1", "NO_HINTS": "0"}

        assert env_value(VAULTSPEC_NO_HINTS, environ) == "1"

    def test_unset_and_blank_both_read_as_nothing(self) -> None:
        assert env_value(NO_COLOR, {}) is None
        assert env_value(NO_COLOR, {"NO_COLOR": ""}) is None
        assert env_value(NO_COLOR, {"NO_COLOR": "   "}) is None

    def test_surrounding_whitespace_is_not_part_of_the_value(self) -> None:
        assert env_value(VAULTSPEC_NO_HINTS, {"VAULTSPEC_NO_HINTS": " 1 "}) == "1"

    def test_an_unregistered_variable_is_refused(self) -> None:
        stray = _stray()

        with pytest.raises(ValueError, match="not declared in a registry"):
            env_value(stray, {stray.env_name: "x"})

    def test_an_equal_copy_of_an_entry_is_still_refused(self) -> None:
        # Registration is by identity: rebuilding an entry field for field is
        # still declaring it a second time.
        copy = ConfigVariable(
            **{
                f.name: getattr(VAULTSPEC_NO_HINTS, f.name)
                for f in fields(ConfigVariable)
                if f.init
            }
        )

        with pytest.raises(ValueError, match="not declared in a registry"):
            env_value(copy, {"VAULTSPEC_NO_HINTS": "1"})


class TestChildEnvironment:
    def test_copies_this_process_and_applies_assignments(self, tmp_path: Path) -> None:
        target = str(tmp_path)

        env = child_environment(
            (VAULTSPEC_MCP_GATEWAY_INVOCATION, "1"), (VAULTSPEC_TARGET_DIR, target)
        )

        assert env == {
            **os.environ,
            "VAULTSPEC_MCP_GATEWAY_INVOCATION": "1",
            "VAULTSPEC_TARGET_DIR": target,
        }

    def test_returns_a_fresh_mapping(self) -> None:
        env = child_environment()
        env["VAULTSPEC_UNDECLARED_CHILD_ONLY"] = "1"

        assert "VAULTSPEC_UNDECLARED_CHILD_ONLY" not in os.environ

    def test_an_unregistered_assignment_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not declared in a registry"):
            child_environment((_stray(), "1"))
