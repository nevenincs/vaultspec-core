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
    edit had succeeded. Exercises the real path: a genuinely missing
    editor command resolved from VAULTSPEC_EDITOR.
    """
    rule = tmp_path / "demo.md"
    rule.write_text("body", encoding="utf-8")

    old_editor = os.environ.get("VAULTSPEC_EDITOR")
    os.environ["VAULTSPEC_EDITOR"] = "vaultspec-no-such-editor-xyz"
    reset_config()
    try:
        with pytest.raises(VaultSpecError, match="Could not launch editor"):
            resources.resource_edit("demo", base_dir=tmp_path, label="Rule")
    finally:
        if old_editor is None:
            os.environ.pop("VAULTSPEC_EDITOR", None)
        else:
            os.environ["VAULTSPEC_EDITOR"] = old_editor
        reset_config()
