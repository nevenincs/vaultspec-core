"""Non-destructive adoption of tracked-but-unmanifested framework projections.

Reproduces a fresh clone of a project that tracks its canonical ``.vaultspec/``
tree and provider projections while correctly ignoring the per-machine
``providers.json``, and pins the contract that such a workspace is adopted by an
ordinary run rather than forced.

Every assertion reads real on-disk state.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.commands import install_run
from vaultspec_core.core.diagnosis import diagnose
from vaultspec_core.core.diagnosis.collectors import collect_framework_presence
from vaultspec_core.core.diagnosis.signals import (
    FrameworkSignal,
    ResolutionAction,
)
from vaultspec_core.core.enums import CliAction
from vaultspec_core.core.executor import execute_plan
from vaultspec_core.core.manifest import (
    ManifestData,
    create_manifest_exclusive,
    read_manifest_data,
)
from vaultspec_core.core.resolver import resolve
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


@pytest.fixture
def fresh_clone(tmp_path: Path) -> WorkspaceFactory:
    """A workspace with tracked framework content and no runtime manifest."""
    factory = WorkspaceFactory(tmp_path)
    factory.install()
    factory.delete_manifest()
    return factory


# ---- Signal classification --------------------------------------------------


class TestFrameworkSignalClassification:
    """The manifest's legitimate absence must not read as corruption."""

    def test_tracked_content_without_manifest_is_adoptable(
        self, fresh_clone: WorkspaceFactory
    ):
        assert not fresh_clone.manifest_path.exists()
        assert collect_framework_presence(fresh_clone.path) is FrameworkSignal.ADOPTABLE

    def test_unparseable_manifest_remains_corrupted(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install().corrupt_manifest()

        assert collect_framework_presence(tmp_path) is FrameworkSignal.CORRUPTED

    def test_manifest_missing_installed_key_remains_corrupted(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.manifest_path.write_text(json.dumps({"version": "2.0"}), "utf-8")

        assert collect_framework_presence(tmp_path) is FrameworkSignal.CORRUPTED

    def test_empty_framework_dir_without_manifest_remains_corrupted(
        self, tmp_path: Path
    ):
        # A bare .vaultspec/ carrying none of the seeded resource categories is
        # not an adoptable clone, it is a broken directory.
        (tmp_path / ".vaultspec").mkdir()

        assert collect_framework_presence(tmp_path) is FrameworkSignal.CORRUPTED

    def test_installed_workspace_is_present(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install()

        assert collect_framework_presence(tmp_path) is FrameworkSignal.PRESENT


# ---- Resolution -------------------------------------------------------------


class TestAdoptionResolution:
    """Adoption is an additive path and must not be gated on --force."""

    def test_install_plans_adoption_without_force(self, fresh_clone: WorkspaceFactory):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)

        assert plan.conflicts == []
        assert any(
            step.action is ResolutionAction.ADOPT_FRAMEWORK for step in plan.steps
        )

    def test_install_no_longer_demands_force_to_repair(
        self, fresh_clone: WorkspaceFactory
    ):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)

        assert not any("--force to repair" in c for c in plan.conflicts)

    def test_sync_plans_adoption_then_sync(self, fresh_clone: WorkspaceFactory):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.SYNC, "all", force=False)

        actions = [step.action for step in plan.steps]
        assert ResolutionAction.ADOPT_FRAMEWORK in actions
        assert actions.index(ResolutionAction.ADOPT_FRAMEWORK) < actions.index(
            ResolutionAction.SYNC
        )

    def test_uninstall_adopts_before_removing(self, fresh_clone: WorkspaceFactory):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.UNINSTALL, "all", force=False)

        assert any(
            step.action is ResolutionAction.ADOPT_FRAMEWORK for step in plan.steps
        )

    def test_corrupted_manifest_still_requires_force_on_install(self, tmp_path: Path):
        # The adoption relaxation must not leak into genuine corruption.
        WorkspaceFactory(tmp_path).install().corrupt_manifest()
        diag = diagnose(tmp_path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)

        assert any("--force" in conflict for conflict in plan.conflicts)


# ---- Divergence refusal -----------------------------------------------------


class TestDivergenceRefusal:
    """Adoption names, and refuses to destroy, locally divergent projections."""

    def test_diverged_projection_is_detected(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude").delete_manifest()

        diag = diagnose(tmp_path, scope="framework")

        assert diag.divergent_projections, "diverged projection was not detected"

    def test_adoption_refuses_and_names_the_paths(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude").delete_manifest()

        diag = diagnose(tmp_path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)

        assert plan.conflicts, "divergent adoption was not refused"
        conflict = plan.conflicts[0]
        for path in diag.divergent_projections:
            assert path in conflict

    def test_cli_refusal_leaves_divergent_content_untouched(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude").delete_manifest()

        diverged = (
            tmp_path / diagnose(tmp_path, scope="framework").divergent_projections[0]
        )
        before = diverged.read_text(encoding="utf-8")

        result = factory.run("install")

        assert result.exit_code == 1, result.output
        assert diverged.read_text(encoding="utf-8") == before
        assert not factory.manifest_path.exists()

    def test_force_permits_the_destructive_sub_path(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude").delete_manifest()

        diag = diagnose(tmp_path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=True)

        assert plan.conflicts == []

    def test_clean_clone_is_not_refused(self, fresh_clone: WorkspaceFactory):
        diag = diagnose(fresh_clone.path, scope="framework")

        assert diag.divergent_projections == []
        assert resolve(diag, CliAction.INSTALL, "all", force=False).conflicts == []


# ---- Manifest establishment -------------------------------------------------


class TestManifestEstablishment:
    """Establishing manifest state must create, never overwrite."""

    def test_adoption_creates_the_manifest(self, fresh_clone: WorkspaceFactory):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)
        result = execute_plan(plan, fresh_clone.path)

        assert result.all_succeeded
        assert fresh_clone.manifest_path.exists()

    def test_adopted_manifest_records_providers_found_on_disk(
        self, fresh_clone: WorkspaceFactory
    ):
        diag = diagnose(fresh_clone.path, scope="framework")
        execute_plan(
            resolve(diag, CliAction.INSTALL, "all", force=False), fresh_clone.path
        )

        installed = read_manifest_data(fresh_clone.path).installed
        on_disk = {
            name
            for name, directory in (
                ("claude", ".claude"),
                ("gemini", ".gemini"),
                ("antigravity", ".agents"),
                ("codex", ".codex"),
            )
            if (fresh_clone.path / directory).is_dir()
        }
        assert installed == on_disk

    def test_adoption_touches_no_other_file(self, fresh_clone: WorkspaceFactory):
        before = {
            path: path.read_bytes()
            for path in sorted(fresh_clone.path.rglob("*"))
            if path.is_file()
        }

        diag = diagnose(fresh_clone.path, scope="framework")
        execute_plan(
            resolve(diag, CliAction.INSTALL, "all", force=False), fresh_clone.path
        )

        after = {
            path: path.read_bytes()
            for path in sorted(fresh_clone.path.rglob("*"))
            if path.is_file()
        }
        assert set(after) - set(before) == {fresh_clone.manifest_path}
        for path, content in before.items():
            assert after[path] == content, f"adoption modified {path}"

    def test_exclusive_create_refuses_to_clobber(self, fresh_clone: WorkspaceFactory):
        sentinel = ManifestData(installed={"claude"}, vaultspec_version="9.9.9")
        assert create_manifest_exclusive(fresh_clone.path, sentinel) is True

        loser = ManifestData(installed={"codex"}, vaultspec_version="0.0.1")
        assert create_manifest_exclusive(fresh_clone.path, loser) is False

        # The first writer's state survives intact.
        data = read_manifest_data(fresh_clone.path)
        assert data.installed == {"claude"}
        assert data.vaultspec_version == "9.9.9"

    def test_adoption_converges_against_a_racing_writer(
        self, fresh_clone: WorkspaceFactory
    ):
        diag = diagnose(fresh_clone.path, scope="framework")
        plan = resolve(diag, CliAction.INSTALL, "all", force=False)

        # A concurrent installer wins the race between diagnosis and execution.
        create_manifest_exclusive(
            fresh_clone.path,
            ManifestData(installed={"gemini"}, vaultspec_version="9.9.9", serial=41),
        )

        result = execute_plan(plan, fresh_clone.path)

        assert result.all_succeeded, "adoption failed instead of converging"
        # The racing writer's manifest is the one that survives: adoption added
        # nothing of its own over the top of it.
        data = read_manifest_data(fresh_clone.path)
        assert data.vaultspec_version == "9.9.9"
        assert data.serial >= 42


# ---- End-to-end install -----------------------------------------------------


class TestInstallAdoptsWithoutForce:
    """The reported reproduction: install a fresh clone without --force."""

    def test_install_run_adopts_instead_of_refusing(
        self, fresh_clone: WorkspaceFactory
    ):
        # Previously raised ResourceExistsError demanding --upgrade or --force.
        install_run(path=fresh_clone.path, provider="all", force=False)

        assert fresh_clone.manifest_path.exists()
        assert read_manifest_data(fresh_clone.path).installed

    def test_install_preserves_locally_authored_framework_content(
        self, fresh_clone: WorkspaceFactory
    ):
        authored = fresh_clone.path / ".vaultspec" / "rules" / "team-rule.md"
        authored.write_text("---\nname: team\n---\nOurs.\n", encoding="utf-8")

        builtin = next((fresh_clone.path / ".vaultspec" / "rules").glob("*.builtin.md"))
        customized = builtin.read_text(encoding="utf-8") + "\n<!-- local edit -->\n"
        builtin.write_text(customized, encoding="utf-8")

        install_run(path=fresh_clone.path, provider="all", force=False)

        assert authored.read_text(encoding="utf-8") == "---\nname: team\n---\nOurs.\n"
        assert builtin.read_text(encoding="utf-8") == customized

    def test_cli_install_exits_zero_on_a_fresh_clone(
        self, fresh_clone: WorkspaceFactory
    ):
        result = fresh_clone.run("install")

        assert result.exit_code == 0, result.output
        assert fresh_clone.manifest_path.exists()

    def test_cli_install_converges_on_a_second_run(self, fresh_clone: WorkspaceFactory):
        assert fresh_clone.run("install").exit_code == 0

        # The abnormal state is gone: a re-adoption after the manifest is
        # removed again succeeds without --force, every time.
        fresh_clone.delete_manifest()
        second = fresh_clone.run("install")

        assert second.exit_code == 0, second.output
        assert fresh_clone.manifest_path.exists()

    def test_doctor_reports_adoptable_as_a_warning_not_an_error(
        self, fresh_clone: WorkspaceFactory
    ):
        result = fresh_clone.run("spec", "doctor")

        assert "corrupted" not in result.output.lower()
        assert result.exit_code != 2, result.output

    def test_already_installed_workspace_still_refuses_without_force(
        self, tmp_path: Path
    ):
        from vaultspec_core.core.exceptions import ResourceExistsError

        WorkspaceFactory(tmp_path).install()

        with pytest.raises(ResourceExistsError):
            install_run(path=tmp_path, provider="all", force=False)
