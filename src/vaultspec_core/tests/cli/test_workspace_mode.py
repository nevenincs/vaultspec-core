"""Tests for the committed workspace mode declaration surface."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.core.workspace_mode import (
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceDeclaration,
    read_workspace_declaration,
    resolve_install_mode,
    write_workspace_declaration,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _declaration_path(root: Path) -> Path:
    return root / ".vaultspec" / "workspace.json"


def _write_raw(root: Path, text: str) -> None:
    path = _declaration_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_pyproject(root: Path, *, dependencies: list[str] | None = None) -> None:
    """Write a minimal ``pyproject.toml`` declaring *dependencies*."""
    lines = ["[project]", 'name = "example"', 'version = "0.0.0"']
    if dependencies is not None:
        rendered = ", ".join(f'"{dep}"' for dep in dependencies)
        lines.append(f"dependencies = [{rendered}]")
    (root / "pyproject.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestRoundTrip:
    def test_tool_mode_round_trips(self, factory):
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.TOOL)
        )

        result = read_workspace_declaration(factory.root)
        assert result is not None
        assert result.install_mode is InstallMode.TOOL
        assert result.minimum_vaultspec_version is None
        assert result.schema_version == WORKSPACE_SCHEMA_VERSION

    def test_dependency_mode_with_floor_round_trips(self, factory):
        write_workspace_declaration(
            factory.root,
            WorkspaceDeclaration(
                install_mode=InstallMode.DEPENDENCY,
                minimum_vaultspec_version="0.1.37",
            ),
        )

        result = read_workspace_declaration(factory.root)
        assert result is not None
        assert result.install_mode is InstallMode.DEPENDENCY
        assert result.minimum_vaultspec_version == "0.1.37"

    def test_floor_key_omitted_when_unset(self, factory):
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.TOOL)
        )

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert "minimum_vaultspec_version" not in raw

    def test_write_is_canonical(self, factory):
        write_workspace_declaration(
            factory.root,
            WorkspaceDeclaration(
                install_mode=InstallMode.DEPENDENCY,
                minimum_vaultspec_version="1.2.3",
            ),
        )

        text = _declaration_path(factory.root).read_text(encoding="utf-8")
        assert text.endswith("\n")
        raw = json.loads(text)
        assert list(raw.keys()) == sorted(raw.keys())
        assert raw["schema_version"] == WORKSPACE_SCHEMA_VERSION
        assert raw["install_mode"] == "dependency"

    def test_schema_version_forced_on_write(self, factory):
        write_workspace_declaration(
            factory.root,
            WorkspaceDeclaration(install_mode=InstallMode.TOOL, schema_version="99.0"),
        )

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert raw["schema_version"] == WORKSPACE_SCHEMA_VERSION


class TestMissingFile:
    def test_missing_file_returns_none(self, factory):
        assert read_workspace_declaration(factory.root) is None


class TestCorruptDeclaration:
    def test_corrupt_json_raises(self, factory):
        _write_raw(factory.root, "{not valid json")

        with pytest.raises(VaultSpecError, match="Corrupt workspace declaration"):
            read_workspace_declaration(factory.root)

    def test_non_object_payload_raises(self, factory):
        _write_raw(factory.root, json.dumps(["tool"]))

        with pytest.raises(VaultSpecError, match="expected a JSON object"):
            read_workspace_declaration(factory.root)

    def test_malformed_mode_value_raises(self, factory):
        _write_raw(
            factory.root,
            json.dumps({"schema_version": "1.0", "install_mode": "hybrid"}),
        )

        with pytest.raises(VaultSpecError, match="Invalid install_mode"):
            read_workspace_declaration(factory.root)

    def test_missing_mode_key_raises(self, factory):
        _write_raw(factory.root, json.dumps({"schema_version": "1.0"}))

        with pytest.raises(VaultSpecError, match="Invalid install_mode"):
            read_workspace_declaration(factory.root)


class TestResolvePrecedence:
    """The Q5 precedence chain: explicit > persisted > detected > default."""

    def test_explicit_overrides_persisted_and_detected(self, factory):
        # Detection and the persisted declaration both point at dependency
        # mode; the explicit flag must still win and flip the result to tool.
        _write_pyproject(factory.root, dependencies=["vaultspec-core>=0.1"])
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.DEPENDENCY)
        )

        assert resolve_install_mode(factory.root, InstallMode.TOOL) is InstallMode.TOOL

    def test_persisted_overrides_detected(self, factory):
        # Detection would read dependency evidence from pyproject, but the
        # persisted declaration names tool mode and outranks detection.
        _write_pyproject(factory.root, dependencies=["vaultspec-core>=0.1"])
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.TOOL)
        )

        assert resolve_install_mode(factory.root) is InstallMode.TOOL

    def test_detected_overrides_default(self, factory):
        # No explicit flag and no persisted declaration, so dependency
        # evidence in pyproject outranks the tool-mode default.
        _write_pyproject(factory.root, dependencies=["vaultspec-core>=0.1"])

        assert resolve_install_mode(factory.root) is InstallMode.DEPENDENCY
