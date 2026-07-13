"""Trigger-site tests for the schema migration registry.

These tests cover the three integration surfaces where pending
migrations must run:

- ``install --upgrade`` runs migrations after the upgrade re-seeds
  builtins.
- ``scan_vault`` runs migrations lazily so any vault command sees a
  consistent layout. Tests here use ``vault add`` and
  ``vault feature index`` because they exercise the lazy path against
  a workspace that was deliberately rewound to a pre-migration
  ``vaultspec_version``.
- ``vault check`` (no ``--fix``) warns about pending migrations and
  must not mutate.

The tests use the real ``WorkspaceFactory`` install path against a
real on-disk manifest. No mocks; no patches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data
from vaultspec_core.migrations import reset_workspace_cache
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _running_version() -> str:
    """Return the installed ``vaultspec-core`` version string."""
    from importlib.metadata import version

    return version("vaultspec-core")


def _bind_context(workspace: Path) -> None:
    """Bind the active workspace context to *workspace*.

    The floor constraint reads ``get_context().target_dir`` inside the
    resolver, so the context must point at the workspace whose declaration
    carries the floor.
    """
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    reset_config()
    init_paths(resolve_workspace(target_override=workspace))


@pytest.fixture(autouse=True)
def _reset_caches():
    reset_config()
    reset_workspace_cache()
    yield
    reset_config()
    reset_workspace_cache()


def _plant_legacy_index(workspace: Path, feature: str) -> Path:
    """Plant a legacy root-level index and stale manifest version.

    Returns the legacy file path.
    """
    docs = workspace / ".vault"
    docs.mkdir(parents=True, exist_ok=True)
    legacy = docs / f"{feature}.index.md"
    legacy.write_text(
        "---\n"
        "generated: true\n"
        "tags:\n"
        f"  - '#{feature}'\n"
        "date: '2026-04-30'\n"
        "related: []\n"
        "---\n\n"
        f"# {feature} index\n",
        encoding="utf-8",
    )
    return legacy


def _rewind_manifest(workspace: Path, version: str = "0.1.0") -> None:
    """Set the manifest's ``vaultspec_version`` to a pre-migration value."""
    data = read_manifest_data(workspace)
    data.vaultspec_version = version
    write_manifest_data(workspace, data)


class TestInstallUpgradeTrigger:
    def test_upgrade_runs_pending_migrations(self, tmp_path: Path):
        # Install once, then rewind the manifest and plant a legacy
        # index. The upgrade branch must run the registry before the
        # final manifest write.
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        _rewind_manifest(tmp_path, "0.1.0")
        target = tmp_path / ".vault" / "index" / "alpha.index.md"
        assert not target.exists()

        factory.install("core", upgrade=True)

        assert not legacy.exists(), (
            "install --upgrade must run the registered migration"
        )
        assert target.exists(), "migrated file must land in .vault/index/"

    def test_upgrade_bumps_manifest_version(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        _plant_legacy_index(tmp_path, "alpha")
        _rewind_manifest(tmp_path, "0.1.0")

        factory.install("core", upgrade=True)

        from vaultspec_core.core.helpers import parse_version_tuple

        version = read_manifest_data(tmp_path).vaultspec_version
        assert parse_version_tuple(version) >= parse_version_tuple("0.1.17")

    def test_upgrade_runs_migrations_before_sync_provider(self, tmp_path: Path):
        # Regression for the order trap: ``sync_provider`` ends by writing
        # ``mdata.vaultspec_version = package_version()`` to the manifest.
        # If migrations ran *after* sync, the driver would read the
        # already-bumped version and skip every entry whose
        # ``target_version`` equals the current release. The upgrade
        # branch must run the registry before the sync so the registry
        # sees the real pre-upgrade manifest version.
        #
        # We rewind to a version one tick below the migration target and
        # plant a legacy artefact that only the registry knows how to
        # migrate. If the order regresses, ``sync_provider`` bumps the
        # version first and the artefact survives.
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "beta")
        _rewind_manifest(tmp_path, "0.1.16")
        target = tmp_path / ".vault" / "index" / "beta.index.md"
        assert not target.exists()

        factory.install("core", upgrade=True)

        assert not legacy.exists(), (
            "sync_provider must not bump vaultspec_version before "
            "run_pending_migrations gets a chance to read the "
            "pre-upgrade manifest"
        )
        assert target.exists(), "migrated file must land in .vault/index/"


class TestScannerLazyTrigger:
    def test_vault_add_migrates_first(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        _rewind_manifest(tmp_path, "0.1.0")
        target = tmp_path / ".vault" / "index" / "alpha.index.md"

        result = factory.run(
            "vault",
            "add",
            "adr",
            "-f",
            "delta",
            "--title",
            "test-adr",
        )

        assert result.exit_code == 0, result.stdout
        assert not legacy.exists(), (
            "vault add must trigger lazy migration before any other action"
        )
        assert target.exists()

    def test_vault_add_ignores_generated_index_collision(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        target = tmp_path / ".vault" / "index" / "alpha.index.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        canonical_before = (
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# canonical alpha\n"
        )
        target.write_text(canonical_before, encoding="utf-8")
        _rewind_manifest(tmp_path, "0.1.0")

        result = factory.run(
            "vault",
            "add",
            "adr",
            "-f",
            "delta",
            "--title",
            "collision-does-not-block",
        )

        assert result.exit_code == 0, result.stdout
        assert not legacy.exists()
        # The lazy migration trigger fired by ``vault add`` runs the
        # 0.1.29 backfill, which seeds the canonical index's missing
        # ``modified:`` stamp from its ``date:``. The collision handling
        # still preserves the body and every other field verbatim.
        canonical_after = (
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nmodified: '2026-04-30'\nrelated: []\n---\n"
            "\n# canonical alpha\n"
        )
        assert target.read_text(encoding="utf-8") == canonical_after

    def test_feature_index_no_split_brain(self, tmp_path: Path):
        # Headline bug: vault feature index in a legacy workspace used
        # to write the new index while leaving the legacy at the root.
        # The lazy migration must run first, then the generator writes
        # exactly one canonical file.
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        # The factory's install creates an .vault/ but no #alpha
        # documents. Plant one so the index generator has something to
        # write.
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        (adr_dir / "2026-04-30-alpha-adr.md").write_text(
            "---\ntags:\n  - '#adr'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha adr\n",
            encoding="utf-8",
        )
        _rewind_manifest(tmp_path, "0.1.0")
        canonical = tmp_path / ".vault" / "index" / "alpha.index.md"

        result = factory.run("vault", "feature", "index", "-f", "alpha")

        assert result.exit_code == 0, result.stdout
        assert not legacy.exists(), "legacy root index must be migrated"
        assert canonical.exists(), "new canonical index must be present"
        # No split-brain: only one file with this stem under .vault/.
        all_indexes = list((tmp_path / ".vault").rglob("alpha.index.md"))
        assert len(all_indexes) == 1, (
            f"expected exactly one alpha.index.md, found: {all_indexes}"
        )

    def test_feature_index_regenerates_after_collision_cleanup(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        canonical = tmp_path / ".vault" / "index" / "alpha.index.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(
            "---\ngenerated: true\ntags:\n  - '#index'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# stale canonical\n",
            encoding="utf-8",
        )
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        (adr_dir / "2026-04-30-alpha-adr.md").write_text(
            "---\ntags:\n  - '#adr'\n  - '#alpha'\n"
            "date: '2026-04-30'\nrelated: []\n---\n\n# alpha adr\n",
            encoding="utf-8",
        )
        _rewind_manifest(tmp_path, "0.1.0")

        result = factory.run("vault", "feature", "index", "-f", "alpha")

        assert result.exit_code == 0, result.stdout
        assert not legacy.exists()
        text = canonical.read_text(encoding="utf-8")
        assert "# `alpha` feature index" in text
        assert "2026-04-30-alpha-adr" in text


class TestVaultCheckWarnsWithoutMutation:
    def test_check_warns_no_fix(self, tmp_path: Path):
        # Set the manifest above every registered target so the lazy
        # trigger short-circuits. The legacy file then stays on disk
        # and the structure checker must still flag it as a pending
        # migration warning rather than silently passing.
        factory = WorkspaceFactory(tmp_path).install("core")
        data = read_manifest_data(tmp_path)
        data.vaultspec_version = "9.9.9"
        write_manifest_data(tmp_path, data)
        legacy = _plant_legacy_index(tmp_path, "alpha")

        result = factory.run("vault", "check", "structure")

        assert "Pending schema migration" in result.stdout or (
            "migration" in result.stdout.lower()
        ), f"expected pending-migration warning, got:\n{result.stdout}"
        assert legacy.exists(), "vault check must not mutate"

    def test_check_fix_does_not_mutate_indexes(self, tmp_path: Path):
        # ``vault check structure --fix`` no longer relocates index
        # files; mutation is owned by the registry only. The lazy
        # trigger is suppressed by setting the manifest above every
        # target so the warning path is exercised in isolation.
        factory = WorkspaceFactory(tmp_path).install("core")
        data = read_manifest_data(tmp_path)
        data.vaultspec_version = "9.9.9"
        write_manifest_data(tmp_path, data)
        legacy = _plant_legacy_index(tmp_path, "alpha")

        result = factory.run("vault", "check", "structure", "--fix")

        assert legacy.exists(), (
            "vault check structure --fix must not relocate legacy "
            "indexes; migration moved to the registry"
        )
        assert "Pending schema migration" in result.stdout


class TestMigrationsCli:
    def test_status_lists_pending(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        _rewind_manifest(tmp_path, "0.1.0")

        result = factory.run("migrations", "status")

        assert result.exit_code == 1, "pending migrations must exit 1"
        assert "pending" in result.stdout
        assert "index_subfolder" in result.stdout

    def test_run_applies_pending(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("core")
        legacy = _plant_legacy_index(tmp_path, "alpha")
        _rewind_manifest(tmp_path, "0.1.0")

        result = factory.run("migrations", "run")

        assert result.exit_code == 0, result.stdout
        assert not legacy.exists()
        # And the manifest version is bumped.
        from vaultspec_core.core.helpers import parse_version_tuple

        version = read_manifest_data(tmp_path).vaultspec_version
        assert parse_version_tuple(version) >= parse_version_tuple("0.1.17")

    def test_status_up_to_date_when_manifest_above_targets(self, tmp_path: Path):
        # ``install_run`` writes the running package version, which on
        # the very release that ships this migration will already
        # cover the 0.1.17 target. Simulate that case by setting the
        # manifest above every registered target.
        factory = WorkspaceFactory(tmp_path).install("core")
        data = read_manifest_data(tmp_path)
        data.vaultspec_version = "9.9.9"
        write_manifest_data(tmp_path, data)

        result = factory.run("migrations", "status")

        assert result.exit_code == 0
        assert "up_to_date" in result.stdout


class TestFloorConstraint:
    """The minimum_vaultspec_version refuse-and-tell floor in the resolver."""

    def _diagnose_and_resolve(self, workspace: Path):
        from vaultspec_core.core.diagnosis.diagnosis import diagnose
        from vaultspec_core.core.enums import CliAction
        from vaultspec_core.core.resolver import resolve

        diag = diagnose(workspace, scope="full")
        return resolve(diag, CliAction.SYNC, target=workspace)

    def test_below_floor_refuses(self, tmp_path: Path) -> None:
        from vaultspec_core.core.enums import InstallMode
        from vaultspec_core.core.exceptions import VaultSpecError
        from vaultspec_core.core.workspace_mode import (
            WorkspaceDeclaration,
            write_workspace_declaration,
        )

        WorkspaceFactory(tmp_path).install("core")
        write_workspace_declaration(
            tmp_path,
            WorkspaceDeclaration(
                install_mode=InstallMode.TOOL,
                minimum_vaultspec_version="999.999.999",
            ),
        )
        _bind_context(tmp_path)

        with pytest.raises(VaultSpecError) as excinfo:
            self._diagnose_and_resolve(tmp_path)

        message = str(excinfo.value)
        assert "999.999.999" in message
        assert _running_version() in message

    def test_at_floor_passes(self, tmp_path: Path) -> None:
        from vaultspec_core.core.enums import InstallMode
        from vaultspec_core.core.resolver import ResolutionPlan
        from vaultspec_core.core.workspace_mode import (
            WorkspaceDeclaration,
            write_workspace_declaration,
        )

        WorkspaceFactory(tmp_path).install("core")
        write_workspace_declaration(
            tmp_path,
            WorkspaceDeclaration(
                install_mode=InstallMode.TOOL,
                minimum_vaultspec_version=_running_version(),
            ),
        )
        _bind_context(tmp_path)

        plan = self._diagnose_and_resolve(tmp_path)
        assert isinstance(plan, ResolutionPlan)

    def test_above_floor_passes(self, tmp_path: Path) -> None:
        from vaultspec_core.core.enums import InstallMode
        from vaultspec_core.core.resolver import ResolutionPlan
        from vaultspec_core.core.workspace_mode import (
            WorkspaceDeclaration,
            write_workspace_declaration,
        )

        WorkspaceFactory(tmp_path).install("core")
        write_workspace_declaration(
            tmp_path,
            WorkspaceDeclaration(
                install_mode=InstallMode.TOOL,
                minimum_vaultspec_version="0.0.1",
            ),
        )
        _bind_context(tmp_path)

        plan = self._diagnose_and_resolve(tmp_path)
        assert isinstance(plan, ResolutionPlan)


class TestFloorConstraintCli:
    """The floor refusal must surface as a clean CLI error, not a traceback.

    The preflight resolve() runs before the mutating command; a below-floor
    workspace must exit non-zero with the remediation message rather than
    letting the raw VaultSpecError escape as an unhandled crash.
    """

    def _floored_workspace(self, workspace: Path) -> None:
        from vaultspec_core.core.enums import InstallMode
        from vaultspec_core.core.workspace_mode import (
            WorkspaceDeclaration,
            write_workspace_declaration,
        )

        WorkspaceFactory(workspace).install("core")
        write_workspace_declaration(
            workspace,
            WorkspaceDeclaration(
                install_mode=InstallMode.TOOL,
                minimum_vaultspec_version="999.999.999",
            ),
        )

    @staticmethod
    def _combined(result) -> str:
        return (result.stdout or "") + "\n" + (result.stderr or "")

    def test_sync_below_floor_exits_clean(self, tmp_path: Path) -> None:
        from vaultspec_core.core.exceptions import VaultSpecError

        self._floored_workspace(tmp_path)
        result = WorkspaceFactory(tmp_path).run("sync")

        assert result.exit_code != 0
        combined = self._combined(result)
        assert "999.999.999" in combined
        assert _running_version() in combined
        # No raw traceback: the refusal was routed through _handle_error, so the
        # captured exception is a clean typer.Exit, never the domain error.
        assert not isinstance(result.exception, VaultSpecError)

    def test_upgrade_below_floor_exits_clean(self, tmp_path: Path) -> None:
        from vaultspec_core.core.exceptions import VaultSpecError

        self._floored_workspace(tmp_path)
        result = WorkspaceFactory(tmp_path).run("install", "--upgrade")

        assert result.exit_code != 0
        combined = self._combined(result)
        assert "999.999.999" in combined
        assert _running_version() in combined
        assert not isinstance(result.exception, VaultSpecError)
