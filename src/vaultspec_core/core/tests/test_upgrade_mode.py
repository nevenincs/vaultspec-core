"""One rule for the mode a legacy workspace is upgraded into.

Two signals decide it: where the workspace's ``pyproject.toml`` places the
package, and how the workspace launches it today. A listing alone is not
enough - a workspace can list a package and still run it as a global tool,
and rewriting that deployment on the listing would break it.

Every workspace here is a real directory with real files, and each package's
launch evidence is supplied the way that package would supply it: core reads
the shape of its committed hook entries, a package that scaffolds no hooks
answers for itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.install_mode import (
    infer_upgrade_mode,
    upgrade_mode_with_provenance,
)
from vaultspec_core.core.workspace_mode import (
    CORE_DISTRIBUTION_NAME,
    ModeProvenance,
    PackageDeclaration,
    write_package_declaration,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

COMPANION = "vaultspec-rag"


def _pyproject(root: Path, body: str) -> Path:
    """Write a real project manifest carrying *body*."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "workspace-under-test"\nversion = "0"\n' + body,
        encoding="utf-8",
    )
    return root


def _runtime_dependency(root: Path, package: str) -> Path:
    return _pyproject(root, f'dependencies = ["{package}>=0.1.0"]\n')


def _dev_group(root: Path, package: str) -> Path:
    return _pyproject(root, f'[dependency-groups]\ndev = ["{package}>=0.1.0"]\n')


class TestPackageWithoutHooks:
    """A package that scaffolds no hooks answers for its own launch."""

    def test_a_listed_package_launched_from_the_workspace_is_a_dependency(
        self, tmp_path: Path
    ) -> None:
        root = _runtime_dependency(tmp_path, COMPANION)

        assert (
            infer_upgrade_mode(root, COMPANION, launch_is_module_run=True)
            is InstallMode.DEPENDENCY
        )

    def test_a_listed_package_launched_as_a_tool_stays_a_tool(
        self, tmp_path: Path
    ) -> None:
        # Upgrading this to dependency mode on the listing alone would rewrite
        # a working global-tool deployment into one the workspace cannot run.
        root = _runtime_dependency(tmp_path, COMPANION)

        assert (
            infer_upgrade_mode(root, COMPANION, launch_is_module_run=False)
            is InstallMode.TOOL
        )

    def test_a_dev_group_listing_resolves_to_dev(self, tmp_path: Path) -> None:
        root = _dev_group(tmp_path, COMPANION)

        assert (
            infer_upgrade_mode(root, COMPANION, launch_is_module_run=True)
            is InstallMode.DEV
        )

    def test_an_unlisted_package_stays_a_tool(self, tmp_path: Path) -> None:
        root = _pyproject(tmp_path, "")

        assert (
            infer_upgrade_mode(root, COMPANION, launch_is_module_run=True)
            is InstallMode.TOOL
        )

    def test_a_workspace_with_no_manifest_stays_a_tool(self, tmp_path: Path) -> None:
        assert (
            infer_upgrade_mode(tmp_path, COMPANION, launch_is_module_run=True)
            is InstallMode.TOOL
        )

    def test_the_evidence_is_only_asked_for_when_it_can_matter(
        self, tmp_path: Path
    ) -> None:
        # Nothing lists the package, so no deployment shape could change the
        # answer, and reading one would be work for a decided question.
        asked = 0

        def evidence() -> bool:
            nonlocal asked
            asked += 1
            return True

        infer_upgrade_mode(tmp_path, COMPANION, launch_is_module_run=evidence)
        assert asked == 0

        infer_upgrade_mode(
            _runtime_dependency(tmp_path, COMPANION),
            COMPANION,
            launch_is_module_run=evidence,
        )
        assert asked == 1


class TestCoresOwnShape:
    """Core's evidence is the shape of its committed hook entries."""

    def test_a_dependency_listing_with_uv_run_hooks_infers_dependency(
        self, tmp_path: Path
    ) -> None:
        root = _runtime_dependency(tmp_path, CORE_DISTRIBUTION_NAME)
        _write_precommit(root, InstallMode.DEPENDENCY)

        resolved = upgrade_mode_with_provenance(root, None)

        assert resolved.mode is InstallMode.DEPENDENCY
        assert resolved.provenance is ModeProvenance.INFERRED

    def test_a_dev_group_listing_with_uv_run_hooks_infers_dev(
        self, tmp_path: Path
    ) -> None:
        # Dev and dependency modes deploy the same launch shape, so a dev
        # listing behind uv-run hooks is a dev workspace, not a tool one.
        root = _dev_group(tmp_path, CORE_DISTRIBUTION_NAME)
        _write_precommit(root, InstallMode.DEV)

        assert upgrade_mode_with_provenance(root, None).mode is InstallMode.DEV

    def test_a_dependency_listing_with_tool_hooks_stays_a_tool(
        self, tmp_path: Path
    ) -> None:
        root = _runtime_dependency(tmp_path, CORE_DISTRIBUTION_NAME)
        _write_precommit(root, InstallMode.TOOL)

        assert upgrade_mode_with_provenance(root, None).mode is InstallMode.TOOL

    def test_a_listing_with_no_hooks_at_all_stays_a_tool(self, tmp_path: Path) -> None:
        root = _runtime_dependency(tmp_path, CORE_DISTRIBUTION_NAME)

        assert upgrade_mode_with_provenance(root, None).mode is InstallMode.TOOL

    def test_a_requested_mode_is_not_inferred(self, tmp_path: Path) -> None:
        root = _runtime_dependency(tmp_path, CORE_DISTRIBUTION_NAME)
        _write_precommit(root, InstallMode.TOOL)

        resolved = upgrade_mode_with_provenance(root, InstallMode.DEPENDENCY)

        assert resolved.mode is InstallMode.DEPENDENCY
        assert resolved.provenance is not ModeProvenance.INFERRED

    def test_a_declared_mode_is_not_inferred(self, tmp_path: Path) -> None:
        root = _runtime_dependency(tmp_path, CORE_DISTRIBUTION_NAME)
        _write_precommit(root, InstallMode.DEPENDENCY)
        write_package_declaration(
            root,
            CORE_DISTRIBUTION_NAME,
            PackageDeclaration(install_mode=InstallMode.TOOL),
        )

        resolved = upgrade_mode_with_provenance(root, None)

        assert resolved.mode is InstallMode.TOOL
        assert resolved.provenance is not ModeProvenance.INFERRED


def _write_precommit(root: Path, mode: InstallMode) -> Path:
    """Write real canonical hook entries provisioned for *mode*."""
    import yaml

    from vaultspec_core.core.precommit import canonical_precommit_hooks_for_mode

    config = {
        "repos": [
            {
                "repo": "local",
                "hooks": list(canonical_precommit_hooks_for_mode(mode)),
            }
        ]
    }
    path = root / ".pre-commit-config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path
