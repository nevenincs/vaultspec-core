"""Guards for what the idempotence stamp counts as a change.

A change the digest misses is the worst failure `init` has: the phase reports
"up to date" and leaves the worktree as it was. For a directory input that
means every way a source can change - an edit, a new file, a deleted one, a
rename, a file deep in a subdirectory, the directory itself appearing - must
move the digest, and an untouched directory must not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dev.init.contract import Phase, Step
from dev.init.stamp import phase_digest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = [pytest.mark.unit]

PHASE = Phase(
    name="tools",
    summary="Render from sources.",
    steps=(Step(name="render", argv=("render",), summary="Render."),),
    inputs=("uv.lock", "sources"),
)


def _populate(root: Path) -> None:
    (root / "uv.lock").write_text("lock\n", encoding="utf-8")
    sources = root / "sources"
    (sources / "nested").mkdir(parents=True)
    (sources / "rule.md").write_text("rule\n", encoding="utf-8")
    (sources / "nested" / "SKILL.md").write_text("skill\n", encoding="utf-8")


def _edit(root: Path) -> None:
    (root / "sources" / "rule.md").write_text("rule, edited\n", encoding="utf-8")


def _edit_nested(root: Path) -> None:
    (root / "sources" / "nested" / "SKILL.md").write_text("edited\n", encoding="utf-8")


def _add(root: Path) -> None:
    (root / "sources" / "new.md").write_text("new\n", encoding="utf-8")


def _remove(root: Path) -> None:
    (root / "sources" / "rule.md").unlink()


def _rename(root: Path) -> None:
    (root / "sources" / "rule.md").rename(root / "sources" / "renamed.md")


@pytest.mark.parametrize(
    "change",
    [_edit, _edit_nested, _add, _remove, _rename],
    ids=["edit", "edit-nested", "add", "remove", "rename"],
)
def test_every_change_to_a_directory_input_makes_the_phase_stale(
    tmp_path: Path, change: Callable[[Path], None]
) -> None:
    _populate(tmp_path)
    before = phase_digest(tmp_path, PHASE)

    change(tmp_path)

    assert phase_digest(tmp_path, PHASE) != before


def test_the_same_sources_digest_the_same_whatever_their_history(
    tmp_path: Path,
) -> None:
    """Only content and paths count, never write order or timestamps."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    _populate(first)
    (second / "sources" / "nested").mkdir(parents=True)
    (second / "sources" / "nested" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (second / "sources" / "rule.md").write_text("draft\n", encoding="utf-8")
    (second / "sources" / "rule.md").write_text("rule\n", encoding="utf-8")
    (second / "uv.lock").write_text("lock\n", encoding="utf-8")

    assert phase_digest(first, PHASE) == phase_digest(second, PHASE)


def test_a_directory_input_that_appears_makes_the_phase_stale(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("lock\n", encoding="utf-8")
    before = phase_digest(tmp_path, PHASE)

    (tmp_path / "sources").mkdir()

    assert phase_digest(tmp_path, PHASE) != before
