"""Tests for the committed workspace mode declaration surface."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.core.workspace_mode import (
    WORKSPACE_SCHEMA_VERSION,
    DependencyEvidence,
    PackageDeclaration,
    WorkspaceDeclaration,
    detect_package_evidence,
    read_package_declaration,
    read_workspace_declaration,
    resolve_install_mode,
    write_package_declaration,
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

    def test_vaultspec_in_default_dev_group_is_dev_evidence(self, factory):
        # PEP 735 default dev group, underscore spelling, mixed with an
        # unrelated requirement: the probe recognizes the distribution as
        # dev-scoped, non-leaking placement and resolves to DEV, not DEPENDENCY.
        (factory.root / "pyproject.toml").write_text(
            '[project]\nname = "example"\nversion = "0.0.0"\n\n'
            "[dependency-groups]\n"
            'dev = ["pytest", "vaultspec_core==0.1.37"]\n',
            encoding="utf-8",
        )

        assert resolve_install_mode(factory.root) is InstallMode.DEV

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


class TestLegacyV1Fold:
    """A schema 1.0 single-key file folds into the schema 2.0 core entry."""

    def test_v1_single_key_file_folds_to_core_entry(self, factory):
        _write_raw(
            factory.root,
            json.dumps(
                {
                    "install_mode": "dependency",
                    "minimum_vaultspec_version": "0.1.37",
                    "schema_version": "1.0",
                }
            ),
        )

        # The facade view and the per-package view agree, and the legacy
        # top-level minimum_vaultspec_version floor is read as the
        # package-relative minimum_version.
        facade = read_workspace_declaration(factory.root)
        assert facade is not None
        assert facade.install_mode is InstallMode.DEPENDENCY
        assert facade.minimum_vaultspec_version == "0.1.37"

        core = read_package_declaration(factory.root, "vaultspec-core")
        assert core is not None
        assert core.install_mode is InstallMode.DEPENDENCY
        assert core.minimum_version == "0.1.37"

    def test_v1_fold_without_floor(self, factory):
        _write_raw(
            factory.root,
            json.dumps({"install_mode": "tool", "schema_version": "1.0"}),
        )

        core = read_package_declaration(factory.root, "vaultspec-core")
        assert core is not None
        assert core.install_mode is InstallMode.TOOL
        assert core.minimum_version is None

    def test_next_write_migrates_legacy_file_to_v2_shape(self, factory):
        # A legacy v1 file gains a rag entry: the folded core entry is preserved
        # and the whole file is rewritten in schema 2.0 shape with no leftover
        # top-level single-key fields.
        _write_raw(
            factory.root,
            json.dumps({"install_mode": "tool", "schema_version": "1.0"}),
        )

        write_package_declaration(
            factory.root, "vaultspec-rag", PackageDeclaration(InstallMode.TOOL)
        )

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert raw["schema_version"] == WORKSPACE_SCHEMA_VERSION
        assert set(raw["packages"]) == {"vaultspec-core", "vaultspec-rag"}
        assert raw["packages"]["vaultspec-core"]["install_mode"] == "tool"
        assert "install_mode" not in raw
        assert "minimum_vaultspec_version" not in raw


class TestSchemaV2RoundTrip:
    """The schema 2.0 per-package map round-trips through the public helpers."""

    def test_dev_mode_round_trips(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.DEV)
        )

        core = read_package_declaration(factory.root, "vaultspec-core")
        assert core is not None
        assert core.install_mode is InstallMode.DEV

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert raw["packages"]["vaultspec-core"]["install_mode"] == "dev"

    def test_dev_mode_round_trips_through_facade(self, factory):
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.DEV)
        )

        result = read_workspace_declaration(factory.root)
        assert result is not None
        assert result.install_mode is InstallMode.DEV

    def test_per_package_floor_round_trips(self, factory):
        write_package_declaration(
            factory.root,
            "vaultspec-rag",
            PackageDeclaration(InstallMode.DEPENDENCY, minimum_version="2.0.0"),
        )

        rag = read_package_declaration(factory.root, "vaultspec-rag")
        assert rag is not None
        assert rag.minimum_version == "2.0.0"

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert raw["packages"]["vaultspec-rag"]["minimum_version"] == "2.0.0"

    def test_floor_omitted_when_unset_in_entry(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.TOOL)
        )

        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert "minimum_version" not in raw["packages"]["vaultspec-core"]

    def test_missing_package_entry_returns_none(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.TOOL)
        )

        assert read_package_declaration(factory.root, "vaultspec-rag") is None


class TestMixedPackageConfig:
    """A workspace declaring two packages resolves each independently."""

    def test_core_dependency_rag_tool_read_independently(self, factory):
        write_package_declaration(
            factory.root,
            "vaultspec-core",
            PackageDeclaration(InstallMode.DEPENDENCY, minimum_version="0.1.37"),
        )
        write_package_declaration(
            factory.root, "vaultspec-rag", PackageDeclaration(InstallMode.TOOL)
        )

        core = read_package_declaration(factory.root, "vaultspec-core")
        rag = read_package_declaration(factory.root, "vaultspec-rag")
        assert core is not None
        assert rag is not None
        assert core.install_mode is InstallMode.DEPENDENCY
        assert core.minimum_version == "0.1.37"
        assert rag.install_mode is InstallMode.TOOL
        assert rag.minimum_version is None

    def test_single_package_write_preserves_sibling(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.TOOL)
        )
        write_package_declaration(
            factory.root,
            "vaultspec-rag",
            PackageDeclaration(InstallMode.DEPENDENCY, minimum_version="2.0.0"),
        )

        # Rewriting core's entry must not touch rag's.
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.DEV)
        )

        rag = read_package_declaration(factory.root, "vaultspec-rag")
        assert rag is not None
        assert rag.install_mode is InstallMode.DEPENDENCY
        assert rag.minimum_version == "2.0.0"

    def test_facade_write_preserves_sibling(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-rag", PackageDeclaration(InstallMode.TOOL)
        )
        write_workspace_declaration(
            factory.root, WorkspaceDeclaration(install_mode=InstallMode.DEPENDENCY)
        )

        rag = read_package_declaration(factory.root, "vaultspec-rag")
        assert rag is not None
        assert rag.install_mode is InstallMode.TOOL

    def test_facade_returns_none_when_only_sibling_declared(self, factory):
        write_package_declaration(
            factory.root, "vaultspec-rag", PackageDeclaration(InstallMode.TOOL)
        )

        assert read_workspace_declaration(factory.root) is None

    def test_pep503_spelling_writes_canonical_key(self, factory):
        write_package_declaration(
            factory.root, "vaultspec_rag", PackageDeclaration(InstallMode.TOOL)
        )

        assert read_package_declaration(factory.root, "vaultspec-rag") is not None
        raw = json.loads(_declaration_path(factory.root).read_text(encoding="utf-8"))
        assert "vaultspec-rag" in raw["packages"]


class TestV2CorruptEntries:
    """Broken schema 2.0 entries fail loud rather than silently dropping."""

    def test_invalid_mode_in_package_entry_raises(self, factory):
        _write_raw(
            factory.root,
            json.dumps(
                {
                    "schema_version": "2.0",
                    "packages": {"vaultspec-core": {"install_mode": "hybrid"}},
                }
            ),
        )

        with pytest.raises(VaultSpecError, match="Invalid install_mode for package"):
            read_workspace_declaration(factory.root)

    def test_non_object_package_entry_raises(self, factory):
        _write_raw(
            factory.root,
            json.dumps(
                {
                    "schema_version": "2.0",
                    "packages": {"vaultspec-core": "tool"},
                }
            ),
        )

        with pytest.raises(VaultSpecError, match="Malformed package entry"):
            read_workspace_declaration(factory.root)

    def test_non_object_packages_map_raises(self, factory):
        _write_raw(
            factory.root,
            json.dumps({"schema_version": "2.0", "packages": ["vaultspec-core"]}),
        )

        with pytest.raises(VaultSpecError, match="Malformed 'packages' map"):
            read_workspace_declaration(factory.root)


def _pyproject(root: Path, body: str) -> Path:
    """Write a ``pyproject.toml`` whose body follows a minimal project table."""
    path = root / "pyproject.toml"
    path.write_text(
        '[project]\nname = "example"\nversion = "0.0.0"\n\n' + body,
        encoding="utf-8",
    )
    return path


class TestDetectionTaxonomy:
    """detect_package_evidence classifies placement on the leak boundary.

    The taxonomy the install-parity ADR draws: runtime-leaking placement
    (project or optional dependencies) is RUNTIME, the default dev group is DEV,
    and a named non-default group or absence is NONE.
    """

    def test_project_dependency_is_runtime(self, factory):
        path = _pyproject(factory.root, 'dependencies = ["vaultspec-core>=0.1"]\n')

        assert (
            detect_package_evidence(path, "vaultspec-core")
            is DependencyEvidence.RUNTIME
        )

    def test_optional_dependency_is_runtime(self, factory):
        # optional-dependencies ship in built metadata and install with their
        # extra, so they leak downstream and read as runtime, not dev.
        path = _pyproject(
            factory.root,
            '[project.optional-dependencies]\nextra = ["vaultspec-core>=0.1"]\n',
        )

        assert (
            detect_package_evidence(path, "vaultspec-core")
            is DependencyEvidence.RUNTIME
        )

    def test_default_dev_group_is_dev(self, factory):
        path = _pyproject(
            factory.root,
            '[dependency-groups]\ndev = ["vaultspec-core>=0.1"]\n',
        )

        assert detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.DEV

    def test_legacy_uv_dev_dependencies_is_dev(self, factory):
        path = _pyproject(
            factory.root,
            '[tool.uv]\ndev-dependencies = ["vaultspec-core>=0.1"]\n',
        )

        assert detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.DEV

    def test_named_non_default_group_is_none(self, factory):
        # A named group is out of detection's scope: it stays inert until
        # enabled with --group, so it is deliberately unclassified.
        path = _pyproject(
            factory.root,
            '[dependency-groups]\nlint = ["vaultspec-core>=0.1"]\n',
        )

        assert (
            detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.NONE
        )

    def test_runtime_outranks_dev_when_in_both(self, factory):
        # Declared in both a runtime set and the dev group: a leaking placement
        # is never masked by a dev declaration.
        path = _pyproject(
            factory.root,
            'dependencies = ["vaultspec-core>=0.1"]\n\n'
            '[dependency-groups]\ndev = ["vaultspec-core>=0.1"]\n',
        )

        assert (
            detect_package_evidence(path, "vaultspec-core")
            is DependencyEvidence.RUNTIME
        )

    def test_underscore_spelling_in_dev_group_matches(self, factory):
        path = _pyproject(
            factory.root,
            '[dependency-groups]\ndev = ["vaultspec_core==0.1.37"]\n',
        )

        assert detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.DEV

    def test_absent_package_is_none(self, factory):
        path = _pyproject(factory.root, 'dependencies = ["pytest", "rich"]\n')

        assert (
            detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.NONE
        )

    def test_missing_file_is_none(self, factory):
        assert (
            detect_package_evidence(factory.root / "pyproject.toml", "vaultspec-core")
            is DependencyEvidence.NONE
        )

    def test_malformed_file_is_none(self, factory):
        path = factory.root / "pyproject.toml"
        path.write_text("this is not valid toml = = =\n", encoding="utf-8")

        assert (
            detect_package_evidence(path, "vaultspec-core") is DependencyEvidence.NONE
        )

    def test_package_parameter_classifies_companion_independently(self, factory):
        # core runtime, rag dev group: each distribution classifies on its own
        # placement, not the file as a whole.
        path = _pyproject(
            factory.root,
            'dependencies = ["vaultspec-core>=0.1"]\n\n'
            '[dependency-groups]\ndev = ["vaultspec-rag>=0.1"]\n',
        )

        assert (
            detect_package_evidence(path, "vaultspec-core")
            is DependencyEvidence.RUNTIME
        )
        assert detect_package_evidence(path, "vaultspec-rag") is DependencyEvidence.DEV


class TestDevPrecedence:
    """DEV enters resolve_install_mode's precedence chain via detection."""

    def test_detected_dev_group_resolves_to_dev(self, factory):
        _pyproject(factory.root, '[dependency-groups]\ndev = ["vaultspec-core>=0.1"]\n')

        assert resolve_install_mode(factory.root) is InstallMode.DEV

    def test_detected_optional_dependency_resolves_to_dependency(self, factory):
        _pyproject(
            factory.root,
            '[project.optional-dependencies]\nextra = ["vaultspec-core>=0.1"]\n',
        )

        assert resolve_install_mode(factory.root) is InstallMode.DEPENDENCY

    def test_detected_named_group_falls_through_to_tool(self, factory):
        _pyproject(
            factory.root, '[dependency-groups]\nlint = ["vaultspec-core>=0.1"]\n'
        )

        assert resolve_install_mode(factory.root) is InstallMode.TOOL

    def test_persisted_dev_outranks_runtime_detection(self, factory):
        # Detection would read runtime evidence, but the persisted DEV
        # declaration outranks detection.
        _pyproject(factory.root, 'dependencies = ["vaultspec-core>=0.1"]\n')
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.DEV)
        )

        assert resolve_install_mode(factory.root) is InstallMode.DEV

    def test_explicit_dev_with_pyproject_is_permitted(self, factory):
        # A pyproject exists but does not yet list vaultspec-core; an explicit
        # --mode dev is still honored since the contributor may be about to add
        # the placement.
        _pyproject(factory.root, 'dependencies = ["pytest"]\n')

        assert resolve_install_mode(factory.root, InstallMode.DEV) is InstallMode.DEV

    def test_explicit_dev_overrides_persisted_and_detected(self, factory):
        _pyproject(factory.root, 'dependencies = ["vaultspec-core>=0.1"]\n')
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.TOOL)
        )

        assert resolve_install_mode(factory.root, InstallMode.DEV) is InstallMode.DEV

    def test_package_parameter_resolves_companion_independently(self, factory):
        # rag persisted DEV, core persisted DEPENDENCY: resolving each package
        # reads only its own entry.
        write_package_declaration(
            factory.root, "vaultspec-core", PackageDeclaration(InstallMode.DEPENDENCY)
        )
        write_package_declaration(
            factory.root, "vaultspec-rag", PackageDeclaration(InstallMode.DEV)
        )

        assert resolve_install_mode(factory.root) is InstallMode.DEPENDENCY
        assert (
            resolve_install_mode(factory.root, package="vaultspec-rag")
            is InstallMode.DEV
        )

    def test_detection_uses_the_named_package(self, factory):
        # Only rag is dev-declared; resolving rag detects DEV while core, absent
        # from the manifest, falls through to the tool default.
        _pyproject(factory.root, '[dependency-groups]\ndev = ["vaultspec-rag>=0.1"]\n')

        assert (
            resolve_install_mode(factory.root, package="vaultspec-rag")
            is InstallMode.DEV
        )
        assert resolve_install_mode(factory.root, package="vaultspec-core") is (
            InstallMode.TOOL
        )


class TestDevRefusal:
    """The impossible-combo refusal extends to DEV, which also needs a manifest."""

    def test_explicit_dev_without_pyproject_raises_with_hint(self, factory):
        with pytest.raises(VaultSpecError) as excinfo:
            resolve_install_mode(factory.root, InstallMode.DEV)

        assert "dev mode" in str(excinfo.value)
        assert "pyproject.toml" in str(excinfo.value)
        assert "--mode tool" in excinfo.value.hint
