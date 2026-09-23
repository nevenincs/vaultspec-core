"""The committed opt-out from managed ``.pre-commit-config.yaml`` scaffolding.

A project that runs its gates explicitly must be able to decline the hook
config once and have that survive every later run. Before the opt-out existed
the file came back on every ``install`` and ``sync``, from four separate call
sites, and was not covered by the managed ``.gitignore`` block even though its
``.lock`` sentinel was - so a sweep-style ``git add -A`` recommitted the hooks.

These tests drive the real filesystem, the real ``install_run``, and the real
CLI; no mocks, patches, or stubs. They pin:

* the scaffold declines when the declaration says so, and still emits when it
  is absent or permissive;
* the decline reaches the doctor's repair executor, and the resolver stops
  planning a repair, so a declined workspace does not report a defect forever
  behind a fix that is now a permanent no-op;
* the managed ``.gitignore`` block lists the config only once declined;
* the CLI verbs write the declaration and are idempotent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.commands import scaffold_precommit
from vaultspec_core.core.gitignore import get_recommended_entries
from vaultspec_core.core.workspace_mode import (
    HooksDeclaration,
    read_hooks_declaration,
    write_hooks_declaration,
)

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

_CONFIG = ".pre-commit-config.yaml"


def _decline(root: Path) -> None:
    write_hooks_declaration(root, HooksDeclaration(pre_commit=False))


def _bare_workspace(root: Path) -> Path:
    """Give *root* the ``.vaultspec/`` directory ``--target`` validation needs."""
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    return root


class TestScaffoldHonoursTheDeclaration:
    def test_declined_workspace_is_not_scaffolded(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _decline(tmp_path)

        caplog.set_level("INFO", logger="vaultspec_core.core.precommit")
        result = scaffold_precommit(tmp_path)

        assert result == []
        assert not (tmp_path / _CONFIG).exists()
        assert any(
            "sets hooks.pre_commit to false" in rec.message for rec in caplog.records
        )

    def test_undeclared_workspace_is_scaffolded(self, tmp_path: Path) -> None:
        """The permissive default: absence is not a decision."""
        result = scaffold_precommit(tmp_path)

        assert result == [(_CONFIG, "precommit")]
        assert (tmp_path / _CONFIG).exists()

    def test_explicitly_enabled_workspace_is_scaffolded(self, tmp_path: Path) -> None:
        write_hooks_declaration(tmp_path, HooksDeclaration(pre_commit=True))

        assert scaffold_precommit(tmp_path) == [(_CONFIG, "precommit")]
        assert (tmp_path / _CONFIG).exists()

    def test_dry_run_reports_nothing_when_declined(self, tmp_path: Path) -> None:
        """The install manifest preview must not advertise a file it won't write."""
        _decline(tmp_path)

        assert scaffold_precommit(tmp_path, dry_run=True) == []

    def test_existing_config_is_left_alone(self, tmp_path: Path) -> None:
        """Declining future scaffolding never deletes what is already there."""
        config = tmp_path / _CONFIG
        config.write_text("repos: []\n", encoding="utf-8")
        _decline(tmp_path)

        assert scaffold_precommit(tmp_path) == []
        assert config.read_text(encoding="utf-8") == "repos: []\n"

    def test_doctor_repair_executor_honours_the_decline(self, tmp_path: Path) -> None:
        """The repair path is a distinct call site and must not resurrect it."""
        from vaultspec_core.core.diagnosis.signals import ResolutionAction
        from vaultspec_core.core.executor import _execute_repair_precommit
        from vaultspec_core.core.resolver_types import ResolutionStep

        _decline(tmp_path)
        _execute_repair_precommit(
            tmp_path,
            ResolutionStep(
                action=ResolutionAction.REPAIR_PRECOMMIT,
                target=str(tmp_path),
                reason="test",
            ),
        )

        assert not (tmp_path / _CONFIG).exists()

    def test_resolver_plans_no_precommit_repair(
        self, factory: WorkspaceFactory
    ) -> None:
        """The doctor must not keep proposing a repair the scaffold declines.

        Otherwise a workspace that made a deliberate choice reports a defect
        forever and the offered fix is a permanent no-op.
        """
        from vaultspec_core.core.diagnosis import diagnose
        from vaultspec_core.core.diagnosis.signals import ResolutionAction
        from vaultspec_core.core.enums import CliAction
        from vaultspec_core.core.resolver import resolve

        factory.install()
        _decline(factory.root)
        (factory.root / _CONFIG).unlink()

        plan = resolve(diagnose(factory.root), CliAction.SYNC, target=factory.root)

        assert not any(
            step.action is ResolutionAction.REPAIR_PRECOMMIT for step in plan.steps
        )


class TestOptOutSurvivesInstall:
    def test_upgrade_does_not_resurrect_the_declined_config(
        self, factory: WorkspaceFactory
    ) -> None:
        """The reported defect: delete the file, run again, it comes back."""
        factory.install()
        assert (factory.root / _CONFIG).exists()

        _decline(factory.root)
        (factory.root / _CONFIG).unlink()

        factory.install(upgrade=True)

        assert not (factory.root / _CONFIG).exists()
        assert read_hooks_declaration(factory.root).pre_commit is False

    def test_install_over_a_committed_declaration_writes_nothing(
        self, factory: WorkspaceFactory
    ) -> None:
        """A teammate cloning a repo whose declaration already declines.

        The committed ``.vaultspec/`` arrives with the checkout, so the first
        local install adopts it rather than scaffolding from nothing - and must
        respect the declaration it just inherited.
        """
        from vaultspec_core.core.commands import install_run

        factory.create_gitignore()
        _decline(factory.root)

        install_run(path=factory.root, provider="all", adopt=True)

        assert not (factory.root / _CONFIG).exists()


class TestManagedGitignoreEntry:
    def test_declined_config_is_ignored(self, factory: WorkspaceFactory) -> None:
        factory.install()
        _decline(factory.root)

        assert f"/{_CONFIG}" in get_recommended_entries(factory.root)

    def test_wanted_config_is_not_ignored(self, factory: WorkspaceFactory) -> None:
        """A wanted config stays team-shared, matching the sharing policy."""
        factory.install()

        entries = get_recommended_entries(factory.root)
        assert f"/{_CONFIG}" not in entries
        # The adjacent per-machine sentinel is ignored either way; the
        # asymmetry between the two is deliberate, not an oversight.
        assert f"/{_CONFIG}.lock" in entries

    def test_entry_reaches_the_written_block(self, factory: WorkspaceFactory) -> None:
        from vaultspec_core.core.enums import ManagedState
        from vaultspec_core.core.gitignore import ensure_gitignore_block

        factory.install()
        _decline(factory.root)
        ensure_gitignore_block(
            factory.root,
            get_recommended_entries(factory.root),
            state=ManagedState.PRESENT,
        )

        text = (factory.root / ".gitignore").read_text(encoding="utf-8")
        assert f"/{_CONFIG}\n" in text


class TestCliVerbs:
    def test_disable_writes_the_declaration(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        from vaultspec_core.tests.cli.conftest import run_vaultspec

        result = run_vaultspec(
            runner, "spec", "precommit", "disable", target=_bare_workspace(factory.root)
        )

        assert result.exit_code == 0, result.output
        assert read_hooks_declaration(factory.root).pre_commit is False

    def test_enable_clears_the_declaration(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        from vaultspec_core.tests.cli.conftest import run_vaultspec

        _decline(factory.root)
        result = run_vaultspec(
            runner, "spec", "precommit", "enable", target=factory.root
        )

        assert result.exit_code == 0, result.output
        assert read_hooks_declaration(factory.root).pre_commit is True

    def test_disable_is_idempotent(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        """An already-satisfied request is success, reported as unchanged."""
        import json

        from vaultspec_core.tests.cli.conftest import run_vaultspec

        _decline(factory.root)
        result = run_vaultspec(
            runner, "spec", "precommit", "disable", "--json", target=factory.root
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["status"] == "unchanged"

    def test_disable_reports_updated_on_first_call(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        import json

        from vaultspec_core.tests.cli.conftest import run_vaultspec

        result = run_vaultspec(
            runner,
            "spec",
            "precommit",
            "disable",
            "--json",
            target=_bare_workspace(factory.root),
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["status"] == "updated"
        assert payload["data"]["pre_commit"] is False


def _hookless_prek(root: Path) -> None:
    """Give *root* a ``prek.toml`` that owns the boundary and carries no hooks."""
    (root / "prek.toml").write_text('[[repos]]\nrepo = "local"\n', encoding="utf-8")


class TestDoctorHonoursTheDecline:
    """A declined workspace is in its requested state, not a stranded one.

    Before the doctor read the declaration, a hook-less ``prek.toml`` reported
    the hooks as stranded and advised ``spec precommit migrate`` - the verb
    that writes the declined hooks back in.
    """

    def test_hookless_prek_is_declined_not_stranded(self, tmp_path: Path) -> None:
        from vaultspec_core.core.diagnosis.collectors import collect_precommit_state
        from vaultspec_core.core.diagnosis.signals import PrecommitSignal

        _decline(tmp_path)
        _hookless_prek(tmp_path)

        assert collect_precommit_state(tmp_path) is PrecommitSignal.DECLINED

    def test_leftover_config_is_reported_and_kept(self, tmp_path: Path) -> None:
        from vaultspec_core.core.diagnosis.collectors import collect_precommit_state
        from vaultspec_core.core.diagnosis.signals import PrecommitSignal

        (tmp_path / _CONFIG).write_text("repos: []\n", encoding="utf-8")
        _decline(tmp_path)

        assert collect_precommit_state(tmp_path) is PrecommitSignal.DECLINED_LEFTOVER
        assert (tmp_path / _CONFIG).read_text(encoding="utf-8") == "repos: []\n"

    def test_doctor_exits_zero_on_hookless_prek(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        import json

        from vaultspec_core.tests.cli.conftest import run_vaultspec

        factory.install()
        _decline(factory.root)
        (factory.root / _CONFIG).unlink()
        _hookless_prek(factory.root)
        factory.sync()

        result = run_vaultspec(runner, "spec", "doctor", "--json", target=factory.root)

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["data"]["precommit"] == "declined"

    def test_doctor_reports_leftover_config_as_info(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        from vaultspec_core.tests.cli.conftest import run_vaultspec

        factory.install()
        _decline(factory.root)
        _hookless_prek(factory.root)
        factory.sync()

        result = run_vaultspec(runner, "spec", "doctor", target=factory.root)

        assert result.exit_code == 0, result.output
        row = next(line for line in result.output.splitlines() if "precommit" in line)
        assert "info" in row
        assert "warn" not in row
        assert (factory.root / _CONFIG).exists()


class TestMigrateHonoursTheDecline:
    """``spec precommit migrate`` must not write the hooks a workspace refused."""

    def test_prek_toml_is_left_byte_identical(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        import json

        from vaultspec_core.tests.cli.conftest import run_vaultspec

        root = _bare_workspace(factory.root)
        _decline(root)
        _hookless_prek(root)
        before = (root / "prek.toml").read_bytes()

        result = run_vaultspec(
            runner, "spec", "precommit", "migrate", "--json", target=root
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["status"] == "declined"
        assert payload["data"]["yaml_removed"] is False
        assert "spec precommit enable" in payload["data"]["detail"]
        assert (root / "prek.toml").read_bytes() == before

    def test_remove_yaml_removes_the_leftover_and_adds_no_hooks(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        import json

        from vaultspec_core.tests.cli.conftest import run_vaultspec

        root = _bare_workspace(factory.root)
        _decline(root)
        _hookless_prek(root)
        (root / _CONFIG).write_text("repos: []\n", encoding="utf-8")
        before = (root / "prek.toml").read_bytes()

        result = run_vaultspec(
            runner,
            "spec",
            "precommit",
            "migrate",
            "--remove-yaml",
            "--json",
            target=root,
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["status"] == "declined"
        assert payload["data"]["yaml_removed"] is True
        assert not (root / _CONFIG).exists()
        assert (root / "prek.toml").read_bytes() == before

    def test_dry_run_keeps_the_leftover(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        _decline(tmp_path)
        (tmp_path / _CONFIG).write_text("repos: []\n", encoding="utf-8")

        result = migrate_hooks_to_prek(tmp_path, dry_run=True, remove_yaml=True)

        assert result.status == "declined"
        assert result.yaml_removed is True
        assert (tmp_path / _CONFIG).exists()


class TestConfigLockSentinel:
    """``/.pre-commit-config.yaml.lock`` is listed only while something takes it.

    The scaffold is the only thing that locks the config, and it does not run
    once the workspace declines the hooks or ``prek.toml`` owns them.
    """

    def test_default_workspace_lists_the_sentinel(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()

        assert f"/{_CONFIG}.lock" in get_recommended_entries(factory.root)

    def test_declined_workspace_omits_the_sentinel(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        _decline(factory.root)

        entries = get_recommended_entries(factory.root)

        assert f"/{_CONFIG}.lock" not in entries
        assert f"/{_CONFIG}" in entries

    def test_prek_owned_workspace_omits_the_sentinel(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        _hookless_prek(factory.root)

        assert f"/{_CONFIG}.lock" not in get_recommended_entries(factory.root)

    def test_sync_removes_the_sentinel_beside_a_leftover_config(
        self, factory: WorkspaceFactory
    ) -> None:
        """A sentinel no longer ignored must not linger as untracked noise."""
        factory.install()
        sentinel = factory.root / f"{_CONFIG}.lock"
        assert sentinel.is_file()
        _decline(factory.root)

        factory.sync()

        assert (factory.root / _CONFIG).exists()
        assert not sentinel.exists()
        text = (factory.root / ".gitignore").read_text(encoding="utf-8")
        assert f"/{_CONFIG}.lock\n" not in text
