"""Duplicate listings of vaultspec's commit hooks are surfaced, and repaired when live.

Two different mistakes look alike on disk and must not be treated alike:

- a copy of vaultspec's hooks in a config prek does not read (``.yml`` behind a
  ``.yaml``, or any YAML behind ``prek.toml``) never runs, so it is a warning
  and the operator's file is left alone;
- the config prek does read listing the gate more than once - twice in one
  YAML, two managed blocks in ``prek.toml``, or a managed block beside a
  hand-written copy - runs the gate repeatedly on every commit, so it is an
  error, and the repair verbs remove the extra copies.

Real filesystem, real sync; no test doubles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors import collect_precommit_state
from vaultspec_core.core.diagnosis.signals import PrecommitSignal
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.prek_boundary import (
    MARKER_BEGIN,
    refresh_managed_prek_block,
    render_prek_hook_block,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

_YAML = ".pre-commit-config.yaml"
_YML = ".pre-commit-config.yml"
_GATE = "vaultspec-commit-gate"
_ENTRY = (
    f"  - id: {_GATE}\n"
    "    name: Vaultspec commit gate\n"
    "    entry: uv run --no-sync vaultspec-core commit-gate\n"
    "    always_run: true\n"
    "    language: system\n"
    "    pass_filenames: true\n"
)
_ONCE = "repos:\n- repo: local\n  hooks:\n" + _ENTRY
_TWICE = _ONCE + _ENTRY
_BLOCK = render_prek_hook_block(InstallMode.DEPENDENCY)
_HAND_WRITTEN = (
    '[[repos]]\nrepo = "local"\n\n[[repos.hooks]]\n'
    f'id = "{_GATE}"\nentry = "my own gate command"\nlanguage = "system"\n'
)


def _gate_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count(f"{_GATE}")


class TestShadowedCopiesWarn:
    def test_a_yml_behind_a_yaml_is_shadowed(self, tmp_path: Path) -> None:
        (tmp_path / _YAML).write_text(_ONCE, encoding="utf-8")
        (tmp_path / _YML).write_text(_ONCE, encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.SHADOWED

    def test_a_yaml_behind_prek_toml_is_shadowed(self, tmp_path: Path) -> None:
        (tmp_path / "prek.toml").write_text(_BLOCK, encoding="utf-8")
        (tmp_path / _YAML).write_text(_ONCE, encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.SHADOWED

    def test_a_retired_hook_in_the_unread_file_counts_too(self, tmp_path: Path) -> None:
        (tmp_path / _YAML).write_text(_ONCE, encoding="utf-8")
        (tmp_path / _YML).write_text(
            "repos:\n- repo: local\n  hooks:\n  - id: vault-fix\n    entry: x\n",
            encoding="utf-8",
        )

        assert collect_precommit_state(tmp_path) is PrecommitSignal.SHADOWED

    def test_sync_leaves_the_shadowed_file_to_the_operator(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        (factory.root / _YML).write_text(_ONCE, encoding="utf-8")

        factory.sync()

        assert (factory.root / _YML).read_text(encoding="utf-8") == _ONCE


class TestLiveDuplicatesAreErrorsAndRepaired:
    def test_twice_in_one_yaml_is_duplicated(self, tmp_path: Path) -> None:
        (tmp_path / _YAML).write_text(_TWICE, encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.DUPLICATED

    def test_sync_removes_the_extra_yaml_copy_and_says_so(
        self, factory: WorkspaceFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        factory.install()
        (factory.root / _YAML).write_text(_TWICE, encoding="utf-8")
        caplog.set_level("WARNING", logger="vaultspec_core.core.precommit")

        factory.sync()

        assert _gate_count(factory.root / _YAML) == 1
        assert any("Removed duplicate" in r.message for r in caplog.records)
        assert collect_precommit_state(factory.root) is not PrecommitSignal.DUPLICATED

    def test_a_gate_in_a_second_local_repo_is_not_copied_into_the_first(
        self, tmp_path: Path
    ) -> None:
        """Every local repo runs, so the scaffold must see them all."""
        from vaultspec_core.core.precommit import scaffold_precommit

        text = (
            "repos:\n- repo: local\n  hooks:\n  - id: ruff\n    entry: ruff\n"
            "- repo: local\n  hooks:\n" + _ENTRY
        )
        (tmp_path / _YAML).write_text(text, encoding="utf-8")

        scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        assert _gate_count(tmp_path / _YAML) == 1
        assert collect_precommit_state(tmp_path) is not PrecommitSignal.DUPLICATED

    def test_two_managed_blocks_are_duplicated_and_collapsed_by_sync(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        (factory.root / _YAML).unlink()
        prek = factory.root / "prek.toml"
        prek.write_text(_BLOCK + "\n" + _BLOCK, encoding="utf-8")
        assert collect_precommit_state(factory.root) is PrecommitSignal.DUPLICATED

        factory.sync()

        text = prek.read_text(encoding="utf-8")
        assert text.count(MARKER_BEGIN) == 1
        assert text.count(_GATE) == 1

    def test_a_hand_written_copy_wins_over_the_managed_block(
        self, tmp_path: Path
    ) -> None:
        prek = tmp_path / "prek.toml"
        prek.write_text(_HAND_WRITTEN + "\n" + _BLOCK, encoding="utf-8")
        assert collect_precommit_state(tmp_path) is PrecommitSignal.DUPLICATED

        change = refresh_managed_prek_block(tmp_path)

        assert change is not None and "removed vaultspec's managed block" in change
        assert prek.read_text(encoding="utf-8") == _HAND_WRITTEN
        assert collect_precommit_state(tmp_path) is not PrecommitSignal.DUPLICATED

    def test_the_release_migration_collapses_duplicate_blocks(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.migrations.m_0_2_5_commit_gate import migrate

        (tmp_path / "prek.toml").write_text(_BLOCK + "\n" + _BLOCK, encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts["prek"] == 1
        assert (tmp_path / "prek.toml").read_text(encoding="utf-8").count(_GATE) == 1


class TestDoctorWeighsThem:
    def _exit_code(self, signal: PrecommitSignal) -> int:
        from vaultspec_core.cli.spec_cmd import doctor_exit_code
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal

        return doctor_exit_code(
            WorkspaceDiagnosis(framework=FrameworkSignal.PRESENT, precommit=signal)
        )

    def test_a_live_duplicate_is_an_error(self) -> None:
        assert self._exit_code(PrecommitSignal.DUPLICATED) == 2

    def test_a_shadowed_copy_is_a_warning(self) -> None:
        assert self._exit_code(PrecommitSignal.SHADOWED) == 1


class TestHandWrittenDuplicatesAreTheOperatorsToFix:
    """A duplicate outside vaultspec's markers is an error no repair may clear."""

    _TWICE_BY_HAND = _HAND_WRITTEN + "\n" + _HAND_WRITTEN

    def test_doctor_reports_it_and_migrate_refuses_it(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        prek = tmp_path / "prek.toml"
        prek.write_text(self._TWICE_BY_HAND, encoding="utf-8")
        assert collect_precommit_state(tmp_path) is PrecommitSignal.DUPLICATED

        result = migrate_hooks_to_prek(tmp_path)

        assert result.status == "conflicting"
        assert "remove the extra copies by hand" in result.detail
        assert prek.read_text(encoding="utf-8") == self._TWICE_BY_HAND

    def test_sync_warns_instead_of_claiming_a_repair(
        self, factory: WorkspaceFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        factory.install()
        (factory.root / _YAML).unlink()
        prek = factory.root / "prek.toml"
        prek.write_text(self._TWICE_BY_HAND, encoding="utf-8")
        caplog.set_level("WARNING", logger="vaultspec_core.core.prek_boundary")

        factory.sync()

        assert prek.read_text(encoding="utf-8") == self._TWICE_BY_HAND
        assert any("by hand" in r.message for r in caplog.records)


class TestPruningLeavesOnlyWhatItEmptied:
    def test_a_first_local_repo_the_merge_emptied_is_removed(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.precommit import scaffold_precommit

        text = (
            "repos:\n- repo: local\n  hooks:\n  - id: vault-fix\n    entry: x\n"
            "- repo: local\n  hooks:\n" + _ENTRY
        )
        (tmp_path / _YAML).write_text(text, encoding="utf-8")

        scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        rendered = (tmp_path / _YAML).read_text(encoding="utf-8")
        assert "hooks: []" not in rendered
        assert rendered.count("repo: local") == 1

    def test_an_empty_stanza_the_operator_wrote_is_kept(self, tmp_path: Path) -> None:
        from vaultspec_core.core.precommit import scaffold_precommit

        text = "repos:\n- repo: local\n  hooks: []\n- repo: local\n  hooks:\n" + _ENTRY
        (tmp_path / _YAML).write_text(text, encoding="utf-8")

        scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        assert (tmp_path / _YAML).read_text(encoding="utf-8").count("repo: local") == 2
