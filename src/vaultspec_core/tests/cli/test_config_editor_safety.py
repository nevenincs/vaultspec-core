"""Tests for config CLI commands and editor safety/resolution."""

from __future__ import annotations

import shutil

import pytest

from vaultspec_core.cli import app
from vaultspec_core.core.exceptions import EditorResolutionError
from vaultspec_core.core.local_config import get_local_config_path, resolve_editor

pytestmark = [pytest.mark.integration]


class TestConfigCli:
    """Verify config get, set, unset, list command operations."""

    def test_config_crud(self, runner, tmp_path):
        # Establish target directory
        target_dir = tmp_path / "project"
        target_dir.mkdir()

        # 1. Config get of unset key should return code 1
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "get", "editor"]
        )
        assert result.exit_code == 1
        assert "Key 'editor' is not set." in result.output

        # 2. Config set should succeed
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "set", "editor", "notepad"]
        )
        assert result.exit_code == 0
        assert "Set 'editor' to 'notepad'" in result.output

        # Verify config file exists on disk
        config_path = get_local_config_path(target_dir)
        assert config_path.is_file()
        config_content = config_path.read_text(encoding="utf-8")
        assert 'editor = "notepad"' in config_content

        # 3. Config get of set key should print the value
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "get", "editor"]
        )
        assert result.exit_code == 0
        assert result.output.strip() == "notepad"

        # 4. Config get --json should return JSON envelope
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "get", "editor", "--json"]
        )
        assert result.exit_code == 0
        import json

        payload = json.loads(result.output)
        assert payload["schema"] == "vaultspec.config.get.v1"
        assert payload["status"] == "unchanged"
        assert payload["data"]["key"] == "editor"
        assert payload["data"]["value"] == "notepad"

        # 5. Config list should print table
        result = runner.invoke(app, ["--target", str(target_dir), "config", "list"])
        assert result.exit_code == 0
        assert "editor" in result.output
        assert "notepad" in result.output

        # 6. Config list --json should return JSON envelope
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "list", "--json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema"] == "vaultspec.config.list.v1"
        assert payload["status"] == "unchanged"
        assert payload["data"]["entries"]["editor"] == "notepad"

        # 7. Config unset should clear the setting
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "unset", "editor"]
        )
        assert result.exit_code == 0
        assert "Unset 'editor'" in result.output

        # Config file should be empty or have deleted key
        config_content = config_path.read_text(encoding="utf-8")
        assert "editor" not in config_content

        # 8. Config get should fail again
        result = runner.invoke(
            app, ["--target", str(target_dir), "config", "get", "editor"]
        )
        assert result.exit_code == 1


class TestEditorResolution:
    """Verify editor resolution precedence ladder.

    Order: flag -> config -> VISUAL -> EDITOR -> vi.
    """

    def test_resolution_ladder(self, tmp_path):
        import os

        # We need real executables that exist on Windows PATH.
        # notepad, cmd, powershell are standard on Windows.
        notepad_exe = shutil.which("notepad")
        cmd_exe = shutil.which("cmd")
        powershell_exe = shutil.which("powershell")

        assert notepad_exe, "notepad not found on PATH"
        assert cmd_exe, "cmd not found on PATH"
        assert powershell_exe, "powershell not found on PATH"

        # Save old values
        old_visual = os.environ.get("VISUAL")
        old_editor = os.environ.get("EDITOR")
        old_vaultspec_editor = os.environ.get("VAULTSPEC_EDITOR")

        try:
            # Clear environment variables first to avoid pollution
            os.environ.pop("VISUAL", None)
            os.environ.pop("EDITOR", None)
            os.environ.pop("VAULTSPEC_EDITOR", None)

            # 1. Fallback to vi (if vi is on PATH, otherwise raises Error)
            vi_exists = shutil.which("vi") is not None
            if vi_exists:
                assert resolve_editor(target_dir=tmp_path) == "vi"
            else:
                with pytest.raises(EditorResolutionError) as excinfo:
                    resolve_editor(target_dir=tmp_path)
                assert "Could not resolve a working text editor" in str(excinfo.value)

            # 2. EDITOR env var should take precedence over vi
            os.environ["EDITOR"] = "powershell"
            assert resolve_editor(target_dir=tmp_path) == "powershell"

            # 3. VISUAL env var should take precedence over EDITOR
            os.environ["VISUAL"] = "cmd"
            assert resolve_editor(target_dir=tmp_path) == "cmd"

            # 4. VAULTSPEC_EDITOR env var should take precedence over VISUAL
            os.environ["VAULTSPEC_EDITOR"] = "powershell"
            assert resolve_editor(target_dir=tmp_path) == "powershell"

            # 5. Local config should take precedence over VAULTSPEC_EDITOR
            from vaultspec_core.core.local_config import set_config_value

            # Write local config
            get_local_config_path(tmp_path)
            set_config_value("editor", "notepad", target_dir=tmp_path)
            assert resolve_editor(target_dir=tmp_path) == "notepad"

            # 6. Editor override flag should take precedence over local config
            assert (
                resolve_editor(editor_override="powershell", target_dir=tmp_path)
                == "powershell"
            )

        finally:
            # Restore environment variables
            if old_visual is None:
                os.environ.pop("VISUAL", None)
            else:
                os.environ["VISUAL"] = old_visual

            if old_editor is None:
                os.environ.pop("EDITOR", None)
            else:
                os.environ["EDITOR"] = old_editor

            if old_vaultspec_editor is None:
                os.environ.pop("VAULTSPEC_EDITOR", None)
            else:
                os.environ["VAULTSPEC_EDITOR"] = old_vaultspec_editor


class TestEditorSubprocessSafety:
    """Verify exit codes 2, 3, 4 under different editor invocation failures."""

    def test_editor_failures_exits(self, runner, synthetic_project):
        # Add a test rule first so we have something to edit
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "add",
                "test-safety-rule",
                "--body",
                "Initial rule content",
            ],
        )
        assert result.exit_code == 0

        # Case 1: Resolution Failure (Nonexistent Editor Binary) -> Exits with code 2
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "test-safety-rule",
                "--editor",
                "nonexistent-editor-binary-xyz",
            ],
        )
        assert result.exit_code == 2
        assert "Error: Could not resolve a working text editor" in result.output

        # Case 2: Subprocess Failure (Editor exits with non-zero code other than 130)
        # -> Exits with code 3
        # We can use cmd.exe to exit with non-zero code on Windows, e.g. "cmd /c exit 5"
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "test-safety-rule",
                "--editor",
                "cmd /c exit 5",
            ],
        )
        assert result.exit_code == 3
        assert "Error: Editor exited with non-zero exit code 5." in result.output

        # Case 3: User Cancellation (Editor exits with code 130) -> Exits with code 4
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "test-safety-rule",
                "--editor",
                "cmd /c exit 130",
            ],
        )
        assert result.exit_code == 4
        assert "Error: Editor edit cancelled by user." in result.output
