"""An install must not place a shell command nobody asked for.

``.vaultspec/hooks/`` and ``.vaultspec/triggers/`` hold commands that run on the
operator's machine - a hook inside the agent's session on every matching tool
call, a trigger on a lifecycle event. Anything bundled in those directories
arrives in every install of every project, which makes a shipped example a
command the operator never chose, one edit away from running.

Both directories still have to exist, because the authoring verbs write into
them and the documentation names them. So the contract is: created, and empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_COMMAND_DIRS = ("hooks", "triggers")


class TestNothingIsSeeded:
    @pytest.mark.parametrize("name", _COMMAND_DIRS)
    def test_the_directory_is_created(self, tmp_path: Path, name: str) -> None:
        WorkspaceFactory(tmp_path).install("all")

        # A directory the documentation names and the installer does not create
        # is a path an operator is told to use and then cannot find.
        assert (tmp_path / ".vaultspec" / name).is_dir()

    @pytest.mark.parametrize("name", _COMMAND_DIRS)
    def test_the_directory_is_empty(self, tmp_path: Path, name: str) -> None:
        WorkspaceFactory(tmp_path).install("all")

        assert list((tmp_path / ".vaultspec" / name).iterdir()) == []

    @pytest.mark.parametrize("name", _COMMAND_DIRS)
    def test_nothing_is_bundled_to_seed_from(self, name: str) -> None:
        from importlib import resources
        from pathlib import Path as _Path

        # The guard against a future example being added to the package: if one
        # were, scaffold's discovery would create the directory from it and copy
        # it into every install, and the two tests above would only catch that
        # for a workspace installed after the change.
        bundled = _Path(str(resources.files("vaultspec_core.builtins"))) / name
        assert not bundled.exists(), (
            f"builtins/{name}/ must stay absent: anything in it is seeded into "
            f"every install, and these directories hold shell commands"
        )

    def test_an_upgrade_does_not_seed_either(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        factory.install("all", upgrade=True)

        for name in _COMMAND_DIRS:
            assert list((tmp_path / ".vaultspec" / name).iterdir()) == []

    @pytest.mark.parametrize("name", _COMMAND_DIRS)
    def test_a_sync_does_not_seed_either(self, tmp_path: Path, name: str) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        factory.sync("all")

        assert list((tmp_path / ".vaultspec" / name).iterdir()) == []


class TestTheEmptyDirectoriesAreNotForeign:
    def test_doctor_does_not_report_them_as_project_code(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")

        # Both are absent from builtins, so the check that derives "ours" from
        # the bundled tree cannot see them and would otherwise call them
        # intruders in the managed directory.
        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output

    def test_the_vault_check_does_not_report_them_as_foreign(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")

        result = factory.run("vault", "check", "all")
        for name in _COMMAND_DIRS:
            assert f".vaultspec/{name}" not in result.output
