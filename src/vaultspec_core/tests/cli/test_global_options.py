"""Tests for global CLI options."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.logging_config import reset_logging

if TYPE_CHECKING:
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.unit
class TestGlobalOptions:
    def test_verbose_flag_exists(self, runner: CliRunner) -> None:
        """--verbose must be offered, in its shared short form."""
        result = runner.invoke(app, ["--help"])
        assert "--verbose" in result.output
        assert "-v," in result.output

    def test_verbose_flag_raises_the_log_level(
        self, runner: CliRunner, factory: WorkspaceFactory
    ) -> None:
        """--verbose asks for INFO, where the bare invocation asks for WARNING."""
        root = factory.install().path

        reset_logging()
        bare = runner.invoke(app, ["--target", str(root), "status"])
        assert bare.exit_code == 0, bare.output
        assert logging.getLogger().level == logging.WARNING

        reset_logging()
        verbose = runner.invoke(app, ["--verbose", "--target", str(root), "status"])
        assert verbose.exit_code == 0, verbose.output
        assert logging.getLogger().level == logging.INFO

        reset_logging()

    def test_target_help_text(self, runner: CliRunner) -> None:
        """--target help must describe target directory."""
        result = runner.invoke(app, ["--help"])
        assert "target directory" in result.output.lower()

    def test_debug_flag_exists(self, runner: CliRunner) -> None:
        """--debug must still exist."""
        result = runner.invoke(app, ["--help"])
        assert "--debug" in result.output

    def test_no_install_completion(self, runner: CliRunner) -> None:
        """--install-completion must not appear in help."""
        result = runner.invoke(app, ["--help"])
        assert "--install-completion" not in result.output

    def test_no_show_completion(self, runner: CliRunner) -> None:
        """--show-completion must not appear in help."""
        result = runner.invoke(app, ["--help"])
        assert "--show-completion" not in result.output
