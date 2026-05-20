"""Unit tests for core resource operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core import resources
from vaultspec_core.core.exceptions import VaultSpecError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def test_resource_edit_raises_clean_error_on_editor_launch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed editor launch must surface a VaultSpecError with a hint.

    Previously the launch error was swallowed (logged with a full
    traceback) and the command returned normally, exiting 0 as if the
    edit had succeeded.
    """
    rule = tmp_path / "demo.md"
    rule.write_text("body", encoding="utf-8")

    def _fail(editor: str, file_path: str) -> None:
        raise FileNotFoundError(2, "No such file or directory", editor)

    monkeypatch.setattr(resources, "_launch_editor", _fail)

    with pytest.raises(VaultSpecError, match="Could not launch editor"):
        resources.resource_edit("demo", base_dir=tmp_path, label="Rule")
