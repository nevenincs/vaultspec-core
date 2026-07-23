"""Unit tests for platform-aware editor command resolution.

These cover :func:`vaultspec_core.core.local_config._command_first_token_on_path`,
which must not mangle a Windows editor path (backslash separators) before the
:func:`shutil.which` lookup.
"""

from __future__ import annotations

import pytest

from vaultspec_core.core.local_config import _command_first_token_on_path

pytestmark = [pytest.mark.unit]


def test_native_absolute_path_resolves(tmp_path):
    """A real editor referenced by its native absolute path resolves.

    On Windows the absolute path uses backslash separators; tokenizing it with
    POSIX quoting rules would consume the backslashes and break the lookup.
    The helper disables POSIX mode on Windows so the path reaches
    :func:`shutil.which` intact.
    """
    editor = tmp_path / "myeditor.bat"
    editor.write_text("@echo off\n", encoding="utf-8")
    editor.chmod(0o755)

    assert _command_first_token_on_path(str(editor)) is True


def test_missing_command_is_rejected():
    """A command whose first token is not on ``PATH`` is rejected."""
    assert _command_first_token_on_path("vaultspec-not-a-real-editor-xyz") is False


def test_blank_command_is_rejected():
    """A whitespace-only command yields no token and is rejected."""
    assert _command_first_token_on_path("   ") is False
