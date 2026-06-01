"""Unit tests for core resource operations."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core import resources
from vaultspec_core.core.exceptions import VaultSpecError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def test_resource_edit_raises_clean_error_on_editor_launch_failure(
    tmp_path: Path,
) -> None:
    """A failed editor launch must surface a VaultSpecError with a hint.

    Previously the launch error was swallowed (logged with a full
    traceback) and the command returned normally, exiting 0 as if the
    edit had succeeded. Exercises the real path with no test doubles: an
    empty PATH plus a genuinely missing VAULTSPEC_EDITOR command means
    shutil.which resolves nothing - not the configured command and not the
    "vi" fallback - so editor resolution fails for real.
    """
    rule = tmp_path / "demo.md"
    rule.write_text("body", encoding="utf-8")

    empty_path_dir = tmp_path / "empty-path"
    empty_path_dir.mkdir()

    overrides = {
        "VAULTSPEC_EDITOR": "vaultspec-no-such-editor-xyz",
        "PATH": str(empty_path_dir),
        "VISUAL": None,
        "EDITOR": None,
    }
    saved = {name: os.environ.get(name) for name in overrides}
    for name, value in overrides.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    reset_config()
    try:
        with pytest.raises(
            VaultSpecError, match="Could not resolve a working text editor"
        ):
            resources.resource_edit("demo", base_dir=tmp_path, label="Rule")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        reset_config()
