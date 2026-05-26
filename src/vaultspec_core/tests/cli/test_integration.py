"""Integration tests for the unified vaultspec CLI and path resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from vaultspec_core.cli import app

pytestmark = [pytest.mark.unit]


class TestPathsEnvBridge:
    """Verify that path overrides (target) propagate correctly."""

    def test_target_override(self, synthetic_project: Path, runner) -> None:
        """--target flag correctly overrides the workspace root."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "vault", "check", "all"]
        )
        # The synthetic_project fixture deterministically surfaces
        # filename-rename warnings. The contract is exit_code 1 (warnings
        # present, not a hard failure) with a non-empty Vault Check
        # report; exit 2 would mean the path override crashed the check
        # pipeline.
        assert result.exit_code == 1, (
            f"vault check all on synthetic_project produced unexpected exit: "
            f"exit={result.exit_code}\n{result.output}"
        )
        assert "Vault Check" in result.output


class TestValidationEdgeCases:
    """Verify error handling for invalid path configurations."""

    def test_target_dir_must_exist(self, tmp_path: Path, runner) -> None:
        """Providing a nonexistent --target should exit with an error."""
        nonexistent = tmp_path / "ghost"
        result = runner.invoke(
            app, ["--target", str(nonexistent), "vault", "check", "all"]
        )
        assert result.exit_code == 1
        assert "does not exist" in result.output
