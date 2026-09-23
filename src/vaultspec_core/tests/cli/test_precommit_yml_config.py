"""The ``.pre-commit-config.yml`` spelling is resolved the way prek resolves it.

prek reads ``prek.toml``, then ``.pre-commit-config.yaml``, then
``.pre-commit-config.yml``, and runs the first it finds. A workspace on the
``.yml`` spelling used to be invisible to core: the scaffold wrote a ``.yaml``
beside it that silently took precedence, the doctor reported no config, and
migrate, uninstall and the lock-sentinel policy never looked at it. Real
filesystem throughout, no test doubles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.commands import CANONICAL_HOOK_IDS, scaffold_precommit
from vaultspec_core.core.diagnosis.collectors import collect_precommit_state
from vaultspec_core.core.diagnosis.signals import PrecommitSignal
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.gitignore import (
    get_recommended_entries,
    prune_orphaned_lock_sentinels,
)
from vaultspec_core.core.prek_boundary import (
    migrate_hooks_to_prek,
    render_prek_hook_block,
)
from vaultspec_core.core.workspace_mode import (
    HooksDeclaration,
    write_hooks_declaration,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

_YAML = ".pre-commit-config.yaml"
_YML = ".pre-commit-config.yml"
_FOREIGN = (
    "repos:\n- repo: local\n  hooks:\n"
    "  - id: ruff\n    entry: ruff\n    language: system\n"
)


def _local_ids(path: Path) -> set[str]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        hook["id"]
        for repo in data["repos"]
        if repo.get("repo") == "local"
        for hook in repo["hooks"]
    }


def _decline(root: Path) -> None:
    write_hooks_declaration(root, HooksDeclaration(pre_commit=False))


class TestScaffold:
    def test_existing_yml_is_managed_in_place(self, tmp_path: Path) -> None:
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")

        result = scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        assert result == [(_YML, "precommit")]
        assert not (tmp_path / _YAML).exists()
        assert _local_ids(tmp_path / _YML) >= CANONICAL_HOOK_IDS | {"ruff"}

    def test_yaml_wins_when_both_exist(self, tmp_path: Path) -> None:
        """prek reads the ``.yaml``, so that is the one managed."""
        (tmp_path / _YAML).write_text(_FOREIGN, encoding="utf-8")
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")

        scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        assert _local_ids(tmp_path / _YAML) >= CANONICAL_HOOK_IDS
        assert (tmp_path / _YML).read_text(encoding="utf-8") == _FOREIGN

    def test_fresh_workspace_still_gets_yaml(self, tmp_path: Path) -> None:
        assert scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY) == [
            (_YAML, "precommit")
        ]
        assert not (tmp_path / _YML).exists()


class TestDoctorCollector:
    def test_yml_config_is_read(self, tmp_path: Path) -> None:
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.NO_HOOKS

    def test_declined_yml_leftover_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")
        _decline(tmp_path)

        assert collect_precommit_state(tmp_path) is PrecommitSignal.DECLINED_LEFTOVER

    def test_yml_beside_healthy_prek_is_orphaned(self, tmp_path: Path) -> None:
        (tmp_path / "prek.toml").write_text(
            render_prek_hook_block(InstallMode.DEPENDENCY), encoding="utf-8"
        )
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.ORPHANED


class TestMigrateRemoveYaml:
    def test_superseded_yml_is_removed(self, tmp_path: Path) -> None:
        (tmp_path / "prek.toml").write_text(
            render_prek_hook_block(InstallMode.DEPENDENCY), encoding="utf-8"
        )
        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")

        result = migrate_hooks_to_prek(
            tmp_path, mode=InstallMode.DEPENDENCY, remove_yaml=True
        )

        assert result.yaml_removed is True
        assert not (tmp_path / _YML).exists()

    def test_declined_leftovers_of_both_spellings_are_removed(
        self, tmp_path: Path
    ) -> None:
        # Each spelling carries only vaultspec's hooks, so each is removed.
        scaffold_precommit(tmp_path)
        (tmp_path / _YML).write_bytes((tmp_path / _YAML).read_bytes())
        _decline(tmp_path)

        result = migrate_hooks_to_prek(tmp_path, remove_yaml=True)

        assert result.status == "declined"
        assert not (tmp_path / _YAML).exists()
        assert not (tmp_path / _YML).exists()


class TestLockSentinels:
    def test_yml_workspace_ignores_its_own_sentinel(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        (factory.root / _YAML).rename(factory.root / _YML)

        entries = get_recommended_entries(factory.root)

        assert f"/{_YML}.lock" in entries
        assert f"/{_YAML}.lock" not in entries

    def test_default_workspace_does_not_list_the_yml_sentinel(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()

        entries = get_recommended_entries(factory.root)

        assert f"/{_YAML}.lock" in entries
        assert f"/{_YML}.lock" not in entries

    def test_declined_workspace_ignores_both_spellings(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        _decline(factory.root)

        entries = get_recommended_entries(factory.root)

        assert {f"/{_YAML}", f"/{_YML}"} <= set(entries)

    def test_unread_spelling_sentinel_is_pruned(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        stray = factory.root / f"{_YML}.lock"
        stray.write_bytes(b"")

        assert f"{_YML}.lock" in prune_orphaned_lock_sentinels(factory.root)
        assert not stray.exists()


class TestUninstall:
    def test_managed_hooks_are_stripped_from_yml(self, tmp_path: Path) -> None:
        from vaultspec_core.core.uninstall import _uninstall_precommit_hooks

        (tmp_path / _YML).write_text(_FOREIGN, encoding="utf-8")
        scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)
        removed: list[tuple[str, str]] = []

        _uninstall_precommit_hooks(tmp_path, dry_run=False, removed=removed)

        assert removed == [(_YML, "precommit")]
        assert _local_ids(tmp_path / _YML) == {"ruff"}
