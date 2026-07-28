"""Regression tests for GH issue #284: sync honours pre-commit hook removal.

Deleting ``.pre-commit-config.yaml``, or stripping every vaultspec hook from
it, is an operator decision. ``sync`` must not resurrect the hooks through
its preflight; instead the sync body's reconcile pass observes the removal
and durably stands management down (``precommit_managed`` flips to
``False``), after which subsequent syncs leave the file alone. ``--skip
precommit`` must reach preflight as well, so a skipped component can never
be re-scaffolded before the main command runs.

All tests drive the real install/sync engine (and the real CLI for the
preflight path) against a ``WorkspaceFactory`` install; no mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.config import reset_config
from vaultspec_core.core.manifest import read_manifest_data
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.integration]

_CONFIG_NAME = ".pre-commit-config.yaml"

_FOREIGN_ONLY_CONFIG = """\
repos:
- repo: local
  hooks:
  - id: my-project-lint
    name: My project lint
    entry: my-lint
    language: system
"""


@pytest.fixture(autouse=True)
def reset() -> Iterator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1"})


class TestSyncStandsDownOnRemoval:
    """The reconcile pass must honour hook removal instead of repairing it."""

    def test_sync_honours_deleted_config(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("claude")
        config = tmp_path / _CONFIG_NAME
        assert config.exists()
        assert read_manifest_data(tmp_path).precommit_managed is True

        config.unlink()
        factory.sync()

        assert not config.exists(), "sync resurrected a deleted pre-commit config"
        assert read_manifest_data(tmp_path).precommit_managed is False

    def test_standdown_is_durable_across_syncs(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("claude")
        (tmp_path / _CONFIG_NAME).unlink()
        factory.sync()
        factory.sync()

        assert not (tmp_path / _CONFIG_NAME).exists()
        assert read_manifest_data(tmp_path).precommit_managed is False

    def test_sync_stands_down_when_hooks_stripped(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("claude")
        config = tmp_path / _CONFIG_NAME
        config.write_text(_FOREIGN_ONLY_CONFIG, encoding="utf-8")

        factory.sync()

        assert config.read_text(encoding="utf-8") == _FOREIGN_ONLY_CONFIG, (
            "sync re-added vaultspec hooks the operator stripped"
        )
        assert read_manifest_data(tmp_path).precommit_managed is False

    def test_skip_precommit_leaves_component_untouched(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("claude")
        (tmp_path / _CONFIG_NAME).unlink()

        factory.sync(skip={"precommit"})

        assert not (tmp_path / _CONFIG_NAME).exists()
        # Skip means "leave alone entirely": the reconcile pass never ran,
        # so the management flag is not flipped either.
        assert read_manifest_data(tmp_path).precommit_managed is True


class TestCliSyncPreflightHonoursRemoval:
    """The #284 repro path: the ``sync`` CLI runs preflight before the body."""

    def test_cli_sync_does_not_resurrect_deleted_config(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        WorkspaceFactory(tmp_path).install("claude")
        (tmp_path / _CONFIG_NAME).unlink()

        result = runner.invoke(app, ["sync", "--target", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert not (tmp_path / _CONFIG_NAME).exists(), (
            "CLI sync preflight resurrected a deleted pre-commit config"
        )
        assert read_manifest_data(tmp_path).precommit_managed is False

    def test_cli_sync_skip_precommit_does_not_rescaffold(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        WorkspaceFactory(tmp_path).install("claude")
        (tmp_path / _CONFIG_NAME).unlink()

        result = runner.invoke(
            app, ["sync", "--target", str(tmp_path), "--skip", "precommit"]
        )

        assert result.exit_code == 0, result.output
        assert not (tmp_path / _CONFIG_NAME).exists()
        assert read_manifest_data(tmp_path).precommit_managed is True
