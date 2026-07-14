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
        core_entry = raw["packages"]["vaultspec-core"]
        assert list(core_entry.keys()) == sorted(core_entry.keys())
        assert core_entry["install_mode"] == "dependency"
        assert core_entry["minimum_version"] == "1.2.3"

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


class TestDetectionSignals:
    """Detection inputs when no explicit flag or persisted declaration exists."""

    def test_absence_of_pyproject_forces_tool(self, factory):
        assert resolve_install_mode(factory.root) is InstallMode.TOOL

    def test_vaultspec_in_project_dependencies_is_dependency_evidence(self, factory):
        _write_pyproject(factory.root, dependencies=["vaultspec-core>=0.1.37"])

        assert resolve_install_mode(factory.root) is InstallMode.DEPENDENCY

    def test_vaultspec_in_dependency_group_is_dependency_evidence(self, factory):
        # PEP 735 dependency group, underscore spelling, mixed with an
        # unrelated requirement: the probe still recognizes the distribution.
        (factory.root / "pyproject.toml").write_text(
            '[project]\nname = "example"\nversion = "0.0.0"\n\n'
            "[dependency-groups]\n"
            'dev = ["pytest", "vaultspec_core==0.1.37"]\n',
            encoding="utf-8",
        )

        assert resolve_install_mode(factory.root) is InstallMode.DEPENDENCY

    def test_pyproject_without_vaultspec_defaults_to_tool(self, factory):
        # A pyproject that exists but does not list vaultspec-core is the
        # "absence of both signals" case and falls through to the default.
        _write_pyproject(factory.root, dependencies=["pytest", "rich"])

        assert resolve_install_mode(factory.root) is InstallMode.TOOL


class TestResolveRefusal:
    """The impossible-combo refusal, exercised in the CI unit gate.

    The end-to-end no-scaffold guarantee lives in the integration-marked
    ``test_ambiguous_states.py``; these unit tests give the refusal and the
    corrupt-declaration fail-fast path coverage under the ``-m unit`` gate that
    the integration file is excluded from.
    """

    def test_dependency_without_pyproject_raises_with_hint(self, factory):
        with pytest.raises(VaultSpecError) as excinfo:
            resolve_install_mode(factory.root, InstallMode.DEPENDENCY)

        assert "dependency mode" in str(excinfo.value)
        assert "--mode tool" in excinfo.value.hint
        assert "pyproject.toml" in excinfo.value.hint

    def test_corrupt_declaration_raises_before_resolution_with_explicit_mode(
        self, factory
    ):
        # An explicit request outranks the persisted declaration, but the
        # declaration is still read and validated first, so a corrupt
        # workspace.json fails fast at resolution rather than later inside the
        # persistence path after migrations and provider sync have run.
        _write_raw(factory.root, "{not valid json")

        with pytest.raises(VaultSpecError, match="Corrupt workspace declaration"):
            resolve_install_mode(factory.root, InstallMode.TOOL)
