"""Tests for global CLI options."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.logging_config import reset_logging

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

#: Wall-clock bound on a child interpreter; see test_cli_live.py's own guard.
_CHILD_HANG_GUARD_SECONDS = 120


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


@pytest.mark.integration
class TestJsonErrorReportingAboveTheCommand:
    """A refusal that fires before a subcommand parses its own --json still
    renders through the canonical envelope, not a prose line on stderr.

    A real subprocess is required here: ``sys.argv`` is what the fix reads,
    and an in-process ``CliRunner`` invocation never touches it, so it would
    prove nothing about the fix under test.
    """

    def test_a_root_callback_refusal_renders_the_json_envelope(
        self, tmp_path: Path
    ) -> None:
        """VAULTSPEC_LOG_LEVEL is refused in the root callback, before Click
        parses the subcommand's own --json option.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vaultspec_core",
                "-t",
                str(tmp_path),
                "install",
                "--json",
            ],
            env={**os.environ, "VAULTSPEC_LOG_LEVEL": "chatty", "NO_COLOR": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CHILD_HANG_GUARD_SECONDS,
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["schema"] == "vaultspec.error.v1"
        assert payload["status"] == "failed"
        assert "VAULTSPEC_LOG_LEVEL" in payload["data"]["message"]

    def test_a_bad_root_variable_without_json_still_prints_prose(
        self, tmp_path: Path
    ) -> None:
        """Without --json anywhere in argv, the refusal stays plain text."""
        result = subprocess.run(
            [sys.executable, "-m", "vaultspec_core", "-t", str(tmp_path), "install"],
            env={**os.environ, "VAULTSPEC_LOG_LEVEL": "chatty", "NO_COLOR": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CHILD_HANG_GUARD_SECONDS,
        )

        assert result.returncode == 1, result.stdout + result.stderr
        assert "VAULTSPEC_LOG_LEVEL" in result.stderr
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)

    def test_a_bad_target_directory_variable_renders_the_json_envelope(
        self, tmp_path: Path
    ) -> None:
        """A per-command --json this call site already knows about, no argv
        sniffing needed: apply_target's own ConfigurationError path.
        """
        missing = tmp_path / "does-not-exist"
        result = subprocess.run(
            [sys.executable, "-m", "vaultspec_core", "status", "--json"],
            cwd=tmp_path,
            env={**os.environ, "VAULTSPEC_TARGET_DIR": str(missing), "NO_COLOR": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CHILD_HANG_GUARD_SECONDS,
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["schema"] == "vaultspec.error.v1"
        assert payload["status"] == "failed"
        assert "VAULTSPEC_TARGET_DIR" in payload["data"]["message"]
