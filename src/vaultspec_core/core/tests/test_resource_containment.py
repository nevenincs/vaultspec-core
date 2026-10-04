"""Resource identifiers must never grant access outside their managed tree."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core import types
from vaultspec_core.core.agents import agents_add
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.core.resources import (
    resource_remove,
    resource_rename,
    resource_show,
)
from vaultspec_core.core.rules import rules_add
from vaultspec_core.core.skills import skills_add

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _context(root: Path) -> types.WorkspaceContext:
    return types.WorkspaceContext(
        root_dir=root,
        target_dir=root,
        rules_src_dir=root / "rules",
        skills_src_dir=root / "skills",
        agents_src_dir=root / "agents",
        system_src_dir=root / "system",
        templates_dir=root / "templates",
        hooks_dir=root / "hooks",
        triggers_dir=root / "triggers",
    )


BAD_NAMES = [
    "",
    ".",
    "..",
    "../outside",
    "..\\outside",
    "/outside",
    "C:/outside",
    "C:outside",
    "\\\\server\\share",
    "nested/name",
    "project/../../outside",
    "project\\..\\outside",
    "name:stream",
    "name.",
    "name ",
    "NUL",
    "con.md",
    "name\x00",
    "%2e%2e%2foutside",
]


@pytest.mark.parametrize("name", BAD_NAMES)
@pytest.mark.parametrize("is_dir", [False, True])
def test_unsafe_names_refused(tmp_path: Path, name: str, is_dir: bool) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    marker = tmp_path / "outside.md"
    marker.write_text("keep", encoding="utf-8")
    for operation in (
        lambda: resource_show(name, base_dir=root, label="Resource", is_dir=is_dir),
        lambda: resource_remove(
            name, base_dir=root, label="Resource", is_dir=is_dir, force=True
        ),
        lambda: resource_rename(
            name, "valid", base_dir=root, label="Resource", is_dir=is_dir
        ),
        lambda: resource_rename(
            "valid", name, base_dir=root, label="Resource", is_dir=is_dir
        ),
    ):
        with pytest.raises(VaultSpecError):
            operation()
        assert root.is_dir()
        assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("is_dir", [False, True])
def test_absolute_existing_victim_survives(tmp_path: Path, is_dir: bool) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    victim = tmp_path / "outside"
    victim.mkdir()
    marker = victim / "SKILL.md" if is_dir else tmp_path / "outside.md"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(VaultSpecError):
        resource_remove(
            str(victim), base_dir=root, label="Resource", is_dir=is_dir, force=True
        )
    with pytest.raises(VaultSpecError):
        resource_show(str(victim), base_dir=root, label="Resource", is_dir=is_dir)
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("kind", ["file", "skill", "skill-file", "project"])
def test_linked_resources_refused(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    for filename in ("item.md", "SKILL.md"):
        (outside / filename).write_text("keep", encoding="utf-8")
    if kind == "file":
        link, target = root / "item.md", outside / "item.md"
    elif kind == "skill-file":
        (root / "item").mkdir()
        link, target = root / "item" / "SKILL.md", outside / "SKILL.md"
    else:
        link = root / ("project" if kind == "project" else "item")
        target = outside
    link.symlink_to(target, target_is_directory=target.is_dir())
    for name in ["item", "project/item"] if kind == "project" else ["item"]:
        with pytest.raises(VaultSpecError):
            resource_show(
                name, base_dir=root, label="Resource", is_dir=kind.startswith("skill")
            )
        with pytest.raises(VaultSpecError):
            resource_remove(
                name,
                base_dir=root,
                label="Resource",
                is_dir=kind.startswith("skill"),
                force=True,
            )
    assert (outside / "item.md").read_text(encoding="utf-8") == "keep"
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == "keep"


def test_confirmation_cannot_replace_skill_with_link(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    skill = root / "item"
    skill.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    def confirm(_prompt: str) -> bool:
        skill.rmdir()
        skill.symlink_to(outside, target_is_directory=True)
        return True

    with pytest.raises(VaultSpecError):
        resource_remove(
            "item", base_dir=root, label="Skill", is_dir=True, confirm_fn=confirm
        )
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("name", BAD_NAMES)
def test_creation_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    token = types.workspace_ctx.set(_context(tmp_path))
    try:
        for create in (rules_add, agents_add, skills_add):
            with pytest.raises(VaultSpecError):
                create(name, force=True, dry_run=True)
    finally:
        types.workspace_ctx.reset(token)


def test_normal_creation_read_rename_remove(tmp_path: Path) -> None:
    token = types.workspace_ctx.set(_context(tmp_path))
    try:
        for path, is_dir in (
            (rules_add("valid-name", content="keep", interactive=False), False),
            (agents_add("valid-name", body="keep", interactive=False), False),
            (skills_add("valid-name", body="keep", interactive=False), True),
        ):
            root = path.parent.parent if is_dir else path.parent
            assert "keep" in resource_show(
                "valid-name", base_dir=root, label="Resource", is_dir=is_dir
            )
            resource_rename(
                "valid-name", "renamed", base_dir=root, label="Resource", is_dir=is_dir
            )
            assert resource_remove(
                "renamed", base_dir=root, label="Resource", is_dir=is_dir, force=True
            )
    finally:
        types.workspace_ctx.reset(token)


@pytest.mark.parametrize(
    "name", ["item", "item.md", "project/item", "project\\item.md"]
)
def test_legacy_project_names_remain_supported(tmp_path: Path, name: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "item.md").write_text("keep", encoding="utf-8")
    assert resource_show(name, base_dir=tmp_path, label="Rule") == "keep"
    assert resource_remove(name, base_dir=tmp_path, label="Rule", force=True)
