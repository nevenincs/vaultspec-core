"""Security regression tests for the editor command surface.

The editor setting is the one place where this package takes a command string
from the user and hands it to the operating system, and it used to hand over
whatever it was given. Anything the user could name got run: the setting was an
"open my file" control by intent and an "execute this" control in fact.

Three channels carried that value, and all three are exercised here: the
per-invocation ``--editor`` flag, the project-local ``.vaultspec/config.toml``
``editor`` key that persists it, and the environment variables that back the
ordinary terminal workflow. The tests assert the closure *and* the workflow -
a user with ``EDITOR=vim`` or ``--editor "code --wait"`` must be no worse off
than before, and a legitimately unusable value must still fail the way it
always did rather than in some new way.

Everything here runs the real CLI over the real filesystem with real
executables on a real ``PATH``. The probe programs are inert: each one writes a
marker file and exits. There is no test double anywhere in this file, and the
environment is configured through the CLI runner's own ``env=`` argument
rather than by patching the interpreter's view of it.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app
from vaultspec_core.config import VAULTSPEC_MCP_GATEWAY_INVOCATION
from vaultspec_core.core.editor import (
    EDITOR_PROGRAM_ALLOWLIST,
    EditorValidationError,
    editor_program_name,
    validate_editor_command,
)
from vaultspec_core.core.local_config import get_local_config_path, resolve_editor

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

pytestmark = [pytest.mark.integration]

#: A program that certainly exists on ``PATH`` and is certainly not an editor.
#: The running interpreter satisfies both: naming it proves the refusal turns
#: on *what the program is* rather than on whether it could be found.
_NON_EDITOR_PROGRAM = "python"


def _write_marker_probe(directory: Path, name: str, marker: Path) -> str:
    """Create a real executable that records that it ran, then exits zero.

    Inert by construction: it writes one file inside the test's own temporary
    directory and does nothing else. Called a *probe* rather than a double
    because it is a genuine program on a genuine ``PATH`` - the suite-quality
    guard rejects ``fake``/``stub`` in a test symbol's name, and here the name
    would be wrong as well as banned.

    Args:
        directory: Directory to write the program into. Prepend it to ``PATH``
            so *name* resolves.
        name: Bare program name, used verbatim as the editor command.
        marker: File the program writes when it runs.

    Returns:
        The bare program name, ready to pass as an editor command.
    """
    if sys.platform == "win32":
        script = directory / f"{name}.cmd"
        script.write_text(
            f'@echo off\r\necho ran> "{marker}"\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
    else:
        script = directory / name
        script.write_text(
            f'#!/bin/sh\necho ran > "{marker}"\nexit 0\n', encoding="utf-8"
        )
        script.chmod(0o755)
    return name


def _clean_env(bindir: Path) -> dict[str, str]:
    """Build a CLI environment with *bindir* as the whole of ``PATH``.

    Every editor environment variable is cleared, so a test asserting on one
    rung of the resolution ladder is not answered by the developer's own
    ambient settings. On Windows the system ``PATH`` is kept alongside
    *bindir*, because ``cmd.exe`` has to stay reachable for a ``.cmd`` launcher
    to run at all.

    Args:
        bindir: Directory holding this test's probe programs.

    Returns:
        The environment mapping to hand to the CLI runner's ``env=``.
    """
    import os

    path = str(bindir)
    if sys.platform == "win32":
        path = path + os.pathsep + os.environ.get("PATH", "")
    env = {"PATH": path}
    for name in (
        "EDITOR",
        "VISUAL",
        "VAULTSPEC_EDITOR",
        VAULTSPEC_MCP_GATEWAY_INVOCATION.env_name,
    ):
        env[name] = ""
    return env


def _add_rule(runner: CliRunner, project: Path, name: str) -> None:
    """Create a rule to edit, failing the test if the scaffold did not land.

    Args:
        runner: The CLI runner.
        project: The installed workspace root.
        name: Rule name to create.
    """
    result = runner.invoke(
        app,
        ["--target", str(project), "spec", "rules", "add", name, "--body", "content"],
    )
    assert result.exit_code == 0, result.output


class TestEditorCommandRules:
    """The validation rules themselves, stated directly."""

    def test_a_program_that_is_not_an_editor_is_refused(self) -> None:
        """An untrusted channel may not nominate an arbitrary program.

        This is the whole of the vulnerability class: the editor setting was
        an execution primitive because nothing ever asked what it named.
        """
        with pytest.raises(EditorValidationError) as excinfo:
            validate_editor_command(
                _NON_EDITOR_PROGRAM, source="the --editor flag", trust="untrusted"
            )
        message = str(excinfo.value)
        assert _NON_EDITOR_PROGRAM in message
        assert "not a known text editor" in message

    def test_the_refusal_states_the_rule_and_the_way_out(self) -> None:
        """A refused user is told what is allowed and how to widen it."""
        with pytest.raises(EditorValidationError) as excinfo:
            validate_editor_command(
                _NON_EDITOR_PROGRAM, source="the --editor flag", trust="untrusted"
            )
        assert "vim" in str(excinfo.value)
        assert "code --wait" in str(excinfo.value)
        assert "VAULTSPEC_EDITOR" in excinfo.value.hint

    @pytest.mark.parametrize(
        "command",
        [
            "vim",
            "code --wait",
            "subl -n -w",
            "nvim -f",
            "emacsclient -c",
        ],
    )
    def test_ordinary_editor_settings_are_accepted(self, command: str) -> None:
        """Editors that carry arguments pass: the allowlist screens the program.

        A "no spaces" rule would have been the easy way to stop an argument
        string, and it would have rejected the settings most people actually
        use.
        """
        assert validate_editor_command(
            command, source="the --editor flag", trust="untrusted"
        )

    @pytest.mark.parametrize(
        "command",
        [
            "vim; touch marker",
            "vim && touch marker",
            "vim | tee marker",
            "vim $(touch marker)",
            "vim `touch marker`",
            "vim %USERPROFILE%",
            'vim "argument\nwith-newline"',
            "vim argument\x00with-nul",
        ],
    )
    def test_command_processor_syntax_is_refused(self, command: str) -> None:
        """Metacharacters are refused even behind an allowlisted program.

        The editor is spawned as an argv list, so these could not inject on
        their own - but the Windows batch launcher path necessarily re-parses
        its arguments, and no real editor setting contains them. The last two
        cases are control characters *inside* a token, which tokenization
        preserves rather than splitting on.
        """
        with pytest.raises(EditorValidationError):
            validate_editor_command(
                command, source="the --editor flag", trust="untrusted"
            )

    def test_the_environment_may_name_an_unlisted_editor(self) -> None:
        """The trusted tier is the escape hatch for an editor nobody listed.

        Setting an environment variable for this process already requires the
        ability to run code as this process, so screening it against the
        allowlist would protect nothing and would strand anyone whose editor
        the list has never heard of.
        """
        assert validate_editor_command(
            "/opt/some-obscure-editor --wait",
            source="the $EDITOR environment variable",
            trust="trusted",
        ) == ["/opt/some-obscure-editor", "--wait"]

    def test_a_path_qualified_editor_requires_a_trusted_source(self) -> None:
        """An allowlisted basename does not authorize an untrusted path."""
        if sys.platform == "win32":
            command = r'"C:\Program Files\Microsoft VS Code\Code.exe" --wait'
        else:
            command = "/usr/local/bin/code --wait"
        with pytest.raises(EditorValidationError, match="bare program name"):
            validate_editor_command(
                command, source="the --editor flag", trust="untrusted"
            )
        assert validate_editor_command(
            command, source="the $EDITOR variable", trust="trusted"
        )

    @pytest.mark.parametrize(
        "command",
        [
            ".vaultspec/vim",
            "./vim",
            "/usr/bin/vim",
            r'".vaultspec\vim.exe"',
            "C:vim",
            r'"C:\tools\vim.exe"',
            r'"\\server\share\vim.exe"',
            r'"\vim.exe"',
        ],
    )
    def test_untrusted_path_forms_are_refused_even_when_missing(
        self, command: str
    ) -> None:
        with pytest.raises(EditorValidationError, match="bare program name"):
            validate_editor_command(
                command, source="the project config", trust="untrusted"
            )

    def test_program_name_normalization_ignores_directory_and_case(self) -> None:
        """The allowlist is keyed by a normalized bare program name."""
        assert editor_program_name("/usr/bin/VIM") == "vim"
        assert "vim" in EDITOR_PROGRAM_ALLOWLIST

    def test_an_empty_command_is_refused(self) -> None:
        """A whitespace-only setting names nothing and is rejected as such."""
        with pytest.raises(EditorValidationError):
            validate_editor_command(
                "   ", source="the --editor flag", trust="untrusted"
            )


class TestEditorFlagVariant:
    """The per-invocation ``--editor`` value, end to end through the CLI."""

    def test_the_flag_cannot_run_a_program_that_is_not_an_editor(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """``spec rules edit --editor <program>`` refuses a non-editor.

        The probe is a real, resolvable executable that records having run, so
        an absent marker is positive evidence that nothing was spawned rather
        than evidence that the command merely failed somewhere.
        """
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "flag-probe-ran.txt"
        probe = _write_marker_probe(bindir, "vsprobe-runner", marker)
        _add_rule(runner, synthetic_project, "flag-variant-rule")

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "flag-variant-rule",
                "--editor",
                probe,
            ],
            env=_clean_env(bindir),
        )

        assert result.exit_code == 2, result.output
        assert "not a known text editor" in result.output
        assert not marker.exists(), "the refused editor command was executed anyway"

    def test_an_allowlisted_editor_with_arguments_still_runs(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """The legitimate workflow is untouched: ``--editor "micro -q"`` works."""
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "editor-ran.txt"
        _write_marker_probe(bindir, "micro", marker)
        _add_rule(runner, synthetic_project, "flag-happy-rule")

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "flag-happy-rule",
                "--editor",
                "micro -q",
            ],
            env=_clean_env(bindir),
        )

        assert result.exit_code == 0, result.output
        assert marker.exists(), "the allowlisted editor was not launched"


class TestPersistedConfigVariant:
    """The ``.vaultspec/config.toml`` ``editor`` key - the same value, delayed."""

    def test_config_set_refuses_to_persist_a_non_editor(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        """``config set editor`` will not write a value it would not run."""
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "config",
                "set",
                "editor",
                _NON_EDITOR_PROGRAM,
            ],
        )

        assert result.exit_code != 0, result.output
        config_path = get_local_config_path(synthetic_project)
        persisted = (
            config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        )
        assert _NON_EDITOR_PROGRAM not in persisted

    def test_a_hand_written_config_is_refused_on_read(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """Validating only on write would be no defence at all.

        The config file is committed with the workspace, so its value can
        arrive by cloning a repository or by an editor's own hand - neither of
        which goes through ``config set``. The read path has to hold on its
        own, so this test writes the file directly.
        """
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "config-probe-ran.txt"
        probe = _write_marker_probe(bindir, "vsprobe-persisted", marker)
        _add_rule(runner, synthetic_project, "config-variant-rule")

        config_path = get_local_config_path(synthetic_project)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f'editor = "{probe}"\n', encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "config-variant-rule",
            ],
            env=_clean_env(bindir),
        )

        assert result.exit_code == 2, result.output
        assert "not a known text editor" in result.output
        assert not marker.exists(), "the persisted editor command was executed anyway"

    def test_a_refused_config_value_can_still_be_cleared(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        """A workspace poisoned by a bad value is not bricked by the fix.

        ``config get``, ``config list`` and ``config unset`` keep working on a
        value the edit path refuses, so the person who inherited it can see it
        and remove it.
        """
        config_path = get_local_config_path(synthetic_project)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f'editor = "{_NON_EDITOR_PROGRAM}"\n', encoding="utf-8")

        shown = runner.invoke(
            app, ["--target", str(synthetic_project), "config", "get", "editor"]
        )
        assert shown.exit_code == 0, shown.output
        assert _NON_EDITOR_PROGRAM in shown.output

        cleared = runner.invoke(
            app, ["--target", str(synthetic_project), "config", "unset", "editor"]
        )
        assert cleared.exit_code == 0, cleared.output
        assert _NON_EDITOR_PROGRAM not in config_path.read_text(encoding="utf-8")


class TestEnvironmentWorkflow:
    """The ordinary terminal workflow, which must not have moved."""

    def test_editor_environment_variable_still_opens_the_editor(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """``EDITOR=vim`` is the common case and keeps working."""
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "env-editor-ran.txt"
        _write_marker_probe(bindir, "vim", marker)
        _add_rule(runner, synthetic_project, "env-variant-rule")

        env = _clean_env(bindir)
        env["EDITOR"] = "vim"
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "env-variant-rule",
            ],
            env=env,
        )

        assert result.exit_code == 0, result.output
        assert marker.exists(), "the environment-configured editor was not launched"

    def test_an_unlisted_editor_works_through_the_environment(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """The documented escape hatch is real, not just described.

        Someone whose editor the allowlist has never heard of has to be able
        to keep working; the environment is where they do it.
        """
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "unlisted-editor-ran.txt"
        probe = _write_marker_probe(bindir, "vsprobe-obscure-editor", marker)
        _add_rule(runner, synthetic_project, "unlisted-editor-rule")

        env = _clean_env(bindir)
        env["VAULTSPEC_EDITOR"] = probe
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "unlisted-editor-rule",
            ],
            env=env,
        )

        assert result.exit_code == 0, result.output
        assert marker.exists(), "the environment escape hatch did not launch"


class TestNonInteractiveInvocation:
    """The marker the MCP gateway stamps on every child it spawns."""

    def test_a_marked_invocation_opens_no_editor_from_any_source(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        """A tool-originated call has no terminal, so nothing is launched.

        The editor here is allowlisted and reachable and would run in a
        terminal. The refusal turns on the invocation, not on the value, which
        is what makes it hold even if some other path were to let an editor
        command through the gateway's flag screening.
        """
        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "gateway-editor-ran.txt"
        _write_marker_probe(bindir, "nano", marker)
        _add_rule(runner, synthetic_project, "gateway-marked-rule")

        env = _clean_env(bindir)
        env["EDITOR"] = "nano"
        env[VAULTSPEC_MCP_GATEWAY_INVOCATION.env_name] = "1"
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "gateway-marked-rule",
            ],
            env=env,
        )

        assert result.exit_code == 2, result.output
        assert "no terminal" in result.output
        assert not marker.exists(), "an editor was launched for a marked invocation"


class TestRepositoryEditorBoundary:
    """Repository executables cannot impersonate allowlisted editors."""

    @pytest.mark.parametrize("channel", ["config", "flag"])
    @pytest.mark.parametrize("resource", ["rules", "skills", "agents", "triggers"])
    def test_repository_editor_path_is_refused(
        self,
        runner: CliRunner,
        synthetic_project: Path,
        tmp_path: Path,
        channel: str,
        resource: str,
    ) -> None:
        marker = tmp_path / "repository-editor-ran.txt"
        _write_marker_probe(synthetic_project / ".vaultspec", "vim", marker)
        command = ".vaultspec/vim.cmd" if sys.platform == "win32" else ".vaultspec/vim"
        created = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                resource,
                "add",
                "repository-editor-rule",
                "--body",
                "content",
            ],
        )
        assert created.exit_code == 0, created.output
        args = [
            "--target",
            str(synthetic_project),
            "spec",
            resource,
            "edit",
            "repository-editor-rule",
        ]
        if channel == "config":
            get_local_config_path(synthetic_project).write_text(
                f'editor = "{command}"\n', encoding="utf-8"
            )
        else:
            args.extend(["--editor", command])

        previous_cwd = os.getcwd()
        try:
            os.chdir(synthetic_project)
            result = runner.invoke(app, args, env=_clean_env(tmp_path))
        finally:
            os.chdir(previous_cwd)

        assert result.exit_code == 2, result.output
        assert "bare program name" in result.output
        assert not marker.exists(), "the repository executable was launched"

    @pytest.mark.parametrize("path_entry", ["", ".", "bin", "absolute", "implicit"])
    def test_repository_path_entries_do_not_shadow_external_editor(
        self,
        runner: CliRunner,
        synthetic_project: Path,
        tmp_path: Path,
        path_entry: str,
    ) -> None:
        bindir = tmp_path / "bin"
        bindir.mkdir()
        trusted_marker = tmp_path / "external-editor-ran.txt"
        repository_marker = tmp_path / "repository-editor-ran.txt"
        _write_marker_probe(bindir, "micro", trusted_marker)
        repository_bin = synthetic_project / "bin"
        repository_bin.mkdir()
        _write_marker_probe(synthetic_project, "micro", repository_marker)
        _write_marker_probe(repository_bin, "micro", repository_marker)
        _add_rule(runner, synthetic_project, "path-shadow-rule")
        get_local_config_path(synthetic_project).write_text(
            'editor = "micro -q"\n', encoding="utf-8"
        )
        env = _clean_env(bindir)
        entry = str(repository_bin) if path_entry == "absolute" else path_entry
        if path_entry != "implicit":
            env["PATH"] = entry + os.pathsep + env["PATH"]
        previous_cwd = os.getcwd()
        try:
            os.chdir(synthetic_project)
            result = runner.invoke(
                app,
                [
                    "--target",
                    str(synthetic_project),
                    "spec",
                    "rules",
                    "edit",
                    "path-shadow-rule",
                ],
                env=env,
            )
        finally:
            os.chdir(previous_cwd)

        assert result.exit_code == 0, result.output
        assert trusted_marker.exists(), "the external editor was not launched"
        assert not repository_marker.exists(), "PATH selected a repository executable"

    @pytest.mark.parametrize("use_context", [False, True])
    def test_untrusted_resolution_remains_untrusted_when_path_changes(
        self,
        runner: CliRunner,
        synthetic_project: Path,
        tmp_path: Path,
        use_context: bool,
    ) -> None:
        from vaultspec_core.core.editor import spawn_editor
        from vaultspec_core.core.exceptions import EditorResolutionError

        bindir = tmp_path / "bin"
        bindir.mkdir()
        external_marker = tmp_path / "external-editor-ran.txt"
        repository_marker = tmp_path / "repository-editor-ran.txt"
        _write_marker_probe(bindir, "micro", external_marker)
        repository_bin = synthetic_project / "bin"
        repository_bin.mkdir()
        _write_marker_probe(repository_bin, "micro", repository_marker)
        with runner.isolation(env=_clean_env(bindir)):
            command = resolve_editor(
                "micro -q", None if use_context else synthetic_project
            )
        env = _clean_env(repository_bin)
        with runner.isolation(env=env), pytest.raises(EditorResolutionError):
            spawn_editor(command, tmp_path / "document.md")

        assert not repository_marker.exists(), "resolution lost the untrusted tier"
        assert not external_marker.exists()

    @pytest.mark.parametrize(
        "link_kind",
        [
            "directory",
            "executable",
            "workspace-alias",
            "indirect-executable",
            "indirect-directory",
        ],
    )
    def test_linked_paths_cannot_select_repository_executables(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path, link_kind: str
    ) -> None:
        from vaultspec_core.core.editor import spawn_editor

        bindir = tmp_path / "bin"
        bindir.mkdir()
        external_marker = tmp_path / "external-editor-ran.txt"
        repository_marker = tmp_path / "repository-editor-ran.txt"
        _write_marker_probe(bindir, "micro", external_marker)
        repository_bin = synthetic_project / "bin"
        repository_bin.mkdir()
        _write_marker_probe(repository_bin, "micro", repository_marker)
        workspace = synthetic_project
        if link_kind in {"directory", "indirect-directory"}:
            entry = tmp_path / "linked-bin"
            if link_kind == "indirect-directory":
                outside_bin = tmp_path / "outside-bin"
                outside_bin.mkdir()
                _write_marker_probe(outside_bin, "micro", repository_marker)
                relay = repository_bin / "relay"
                relay.symlink_to(outside_bin, target_is_directory=True)
                entry.symlink_to(relay, target_is_directory=True)
            else:
                entry.symlink_to(repository_bin, target_is_directory=True)
        elif link_kind in {"executable", "indirect-executable"}:
            entry = tmp_path / "linked-bin"
            entry.mkdir()
            name = "micro.cmd" if sys.platform == "win32" else "micro"
            if link_kind == "indirect-executable":
                outside_bin = tmp_path / "outside-bin"
                outside_bin.mkdir()
                _write_marker_probe(outside_bin, "micro", repository_marker)
                relay = repository_bin / f"relay-{name}"
                relay.symlink_to(outside_bin / name)
                (entry / name).symlink_to(relay)
            else:
                (entry / name).symlink_to(repository_bin / name)
        else:
            workspace = tmp_path / "workspace-alias"
            workspace.symlink_to(synthetic_project, target_is_directory=True)
            outside_bin = tmp_path / "outside-bin"
            outside_bin.mkdir()
            _write_marker_probe(outside_bin, "micro", repository_marker)
            (synthetic_project / "linked-bin").symlink_to(
                outside_bin, target_is_directory=True
            )
            entry = workspace / "linked-bin"
        env = _clean_env(bindir)
        env["PATH"] = str(entry) + os.pathsep + env["PATH"]
        with runner.isolation(env=_clean_env(bindir)):
            command = resolve_editor("micro -q", workspace)
        with runner.isolation(env=env):
            assert spawn_editor(command, tmp_path / "document.md") == 0

        assert external_marker.exists(), "the eligible external editor was not launched"
        assert not repository_marker.exists(), "a linked repository executable ran"

    def test_missing_editor_does_not_fall_back_to_repository_vi(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.exceptions import EditorResolutionError

        repository_bin = synthetic_project / "bin"
        repository_bin.mkdir()
        marker = tmp_path / "repository-vi-ran.txt"
        _write_marker_probe(repository_bin, "vi", marker)
        env = _clean_env(repository_bin)
        env["PATH"] = str(repository_bin)
        with runner.isolation(env=env), pytest.raises(EditorResolutionError):
            resolve_editor("micro", synthetic_project)
        assert not marker.exists()

    def test_external_editor_alias_keeps_its_invocation_name(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.editor import spawn_editor

        bindir = tmp_path / "bin"
        bindir.mkdir()
        marker = tmp_path / "invocation-name.txt"
        if sys.platform == "win32":
            program = bindir / "editor.cmd"
            alias = bindir / "view.cmd"
            content = f'@echo off\r\necho %~n0> "{marker}"\r\nexit /b 0\r\n'
        else:
            program = bindir / "editor"
            alias = bindir / "view"
            content = f'#!/bin/sh\nprintf "%s\\n" "$0" > "{marker}"\nexit 0\n'
        program.write_text(content, encoding="utf-8")
        program.chmod(0o755)
        alias.symlink_to(program)
        with runner.isolation(env=_clean_env(bindir)):
            command = resolve_editor("view", synthetic_project)
            assert spawn_editor(command, tmp_path / "document.md") == 0

        assert marker.read_text(encoding="utf-8").strip() in {"view", str(alias)}

    def test_unresolved_command_cannot_bypass_launch_validation(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.editor import spawn_editor

        with pytest.raises(EditorValidationError, match="bare program name"):
            spawn_editor(".vaultspec/vim", tmp_path / "document.md")
        with pytest.raises(EditorValidationError, match="not a known text editor"):
            spawn_editor("python", tmp_path / "document.md")

    def test_config_write_refuses_editor_paths(
        self, runner: CliRunner, synthetic_project: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "config",
                "set",
                "editor",
                ".vaultspec/vim",
            ],
        )
        assert result.exit_code != 0, result.output
        assert "bare program name" in result.output
        assert not get_local_config_path(synthetic_project).exists()

    def test_interactive_creation_preserves_untrusted_lookup_boundary(
        self, runner: CliRunner, synthetic_project: Path, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.rules import rules_add

        bindir = tmp_path / "bin"
        bindir.mkdir()
        external_marker = tmp_path / "creation-editor-ran.txt"
        repository_marker = tmp_path / "repository-editor-ran.txt"
        _write_marker_probe(bindir, "micro", external_marker)
        repository_bin = synthetic_project / "bin"
        repository_bin.mkdir()
        _write_marker_probe(repository_bin, "micro", repository_marker)
        get_local_config_path(synthetic_project).write_text(
            'editor = "micro -q"\n', encoding="utf-8"
        )
        env = _clean_env(bindir)
        env["PATH"] = str(repository_bin) + os.pathsep + env["PATH"]
        with runner.isolation(env=env):
            result = rules_add("interactive-editor-rule", interactive=True)

        assert result.is_file()
        assert external_marker.exists(), "interactive creation did not open its editor"
        assert not repository_marker.exists(), "creation lost the workspace boundary"

    @pytest.mark.parametrize("include_system_path", [False, True])
    def test_explicit_repository_path_remains_available_in_trusted_environment(
        self,
        runner: CliRunner,
        synthetic_project: Path,
        tmp_path: Path,
        include_system_path: bool,
    ) -> None:
        marker = tmp_path / "trusted-editor-ran.txt"
        directory = synthetic_project / ".vaultspec" / "editor with spaces"
        directory.mkdir()
        _write_marker_probe(directory, "custom-editor", marker)
        suffix = ".cmd" if sys.platform == "win32" else ""
        program = directory / f"custom-editor{suffix}"
        _add_rule(runner, synthetic_project, "trusted-path-rule")
        env = _clean_env(tmp_path)
        if not include_system_path:
            env["PATH"] = str(tmp_path)
            if sys.platform == "win32":
                env["PATHEXT"] = ".CMD"
        env["VAULTSPEC_EDITOR"] = f'"{program}" --wait'
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "edit",
                "trusted-path-rule",
            ],
            env=env,
        )

        assert result.exit_code == 0, result.output
        assert marker.exists(), "the trusted explicit path no longer works"
