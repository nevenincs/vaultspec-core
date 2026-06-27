"""Real-filesystem tests for :func:`resource_rename` (rules/skills/agents).

``resource_rename`` is now driven through the shared ``RenameTransaction``
engine.  These tests exercise the flat-resource and skill-directory rename
paths, the ``ResourceExistsError`` / ``ResourceNotFoundError`` contract,
byte-for-byte rollback on an induced mid-apply failure, and ``base_dir``
containment.  No test doubles are used: every condition is induced through the
real filesystem under a real temporary ``.vaultspec`` tree.
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core import resource_rename
from vaultspec_core.core import types as _types
from vaultspec_core.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    VaultSpecError,
)
from vaultspec_core.vaultcore import parse_frontmatter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def vaultspec(tmp_path: Path) -> Iterator[Path]:
    """Yield a real temp ``.vaultspec`` with source dirs and an active context.

    The workspace context is set so ``resource_rename`` derives the shared
    resource-domain lock sentinel, and is reset on teardown so no state leaks
    into other tests.
    """
    vs = tmp_path / ".vaultspec"
    rules_dir = vs / "rules" / "rules"
    skills_dir = vs / "rules" / "skills"
    agents_dir = vs / "rules" / "agents"
    for d in (rules_dir, skills_dir, agents_dir):
        d.mkdir(parents=True)

    ctx = _types.WorkspaceContext(
        root_dir=tmp_path,
        target_dir=tmp_path,
        rules_src_dir=rules_dir,
        skills_src_dir=skills_dir,
        agents_src_dir=agents_dir,
        system_src_dir=vs / "rules" / "system",
        templates_dir=vs / "rules" / "templates",
        hooks_dir=vs / "rules" / "hooks",
    )
    token = _types._workspace_ctx.set(ctx)
    try:
        yield vs
    finally:
        _types._workspace_ctx.reset(token)


def _write_rule(rules_dir: Path, name: str, *, body: str = "Rule body.\n") -> Path:
    path = rules_dir / f"{name}.md"
    path.write_text(f"---\nname: {name}\n---\n\n{body}", encoding="utf-8")
    return path


def _write_skill(skills_dir: Path, name: str, *, body: str = "Skill body.\n") -> Path:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n\n{body}", encoding="utf-8"
    )
    return skill_dir


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    """Capture every file under *root* keyed by its relative path."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class TestFlatResourceRename:
    def test_rule_rename_rewrites_name_and_moves_file(self, vaultspec: Path) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        old = _write_rule(rules_dir, "old-rule", body="Original prose.\n")

        new_path = resource_rename(
            "old-rule", "new-rule", base_dir=rules_dir, label="Rule"
        )

        assert new_path == rules_dir / "new-rule.md"
        assert not old.exists()
        assert new_path.is_file()
        fm, body = parse_frontmatter(new_path.read_text(encoding="utf-8"))
        assert fm["name"] == "new-rule"
        assert "Original prose." in body

    def test_agent_rename_rewrites_name(self, vaultspec: Path) -> None:
        agents_dir = vaultspec / "rules" / "agents"
        _write_rule(agents_dir, "old-agent")

        new_path = resource_rename(
            "old-agent", "new-agent", base_dir=agents_dir, label="Agent"
        )

        assert new_path == agents_dir / "new-agent.md"
        fm, _ = parse_frontmatter(new_path.read_text(encoding="utf-8"))
        assert fm["name"] == "new-agent"

    def test_rename_collision_raises_resource_exists(self, vaultspec: Path) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        _write_rule(rules_dir, "src-rule")
        _write_rule(rules_dir, "dst-rule")
        before = _snapshot_tree(rules_dir)

        with pytest.raises(ResourceExistsError):
            resource_rename("src-rule", "dst-rule", base_dir=rules_dir, label="Rule")

        assert _snapshot_tree(rules_dir) == before

    def test_rename_missing_raises_resource_not_found(self, vaultspec: Path) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        with pytest.raises(ResourceNotFoundError):
            resource_rename("ghost", "whatever", base_dir=rules_dir, label="Rule")


class TestSkillRename:
    def test_skill_rename_moves_dir_and_rewrites_name(self, vaultspec: Path) -> None:
        skills_dir = vaultspec / "rules" / "skills"
        old_dir = _write_skill(skills_dir, "old-skill", body="Skill prose.\n")
        # An extra resource file in the skill dir must ride the rename intact.
        (old_dir / "reference.md").write_text("ref body\n", encoding="utf-8")

        new_path = resource_rename(
            "old-skill", "new-skill", base_dir=skills_dir, label="Skill", is_dir=True
        )

        assert new_path == skills_dir / "new-skill"
        assert not old_dir.exists()
        assert new_path.is_dir()
        skill_md = new_path / "SKILL.md"
        fm, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        assert fm["name"] == "new-skill"
        assert "Skill prose." in body
        assert (new_path / "reference.md").read_text(encoding="utf-8") == "ref body\n"

    def test_skill_rename_collision_raises_resource_exists(
        self, vaultspec: Path
    ) -> None:
        skills_dir = vaultspec / "rules" / "skills"
        _write_skill(skills_dir, "src-skill")
        _write_skill(skills_dir, "dst-skill")
        before = _snapshot_tree(skills_dir)

        with pytest.raises(ResourceExistsError):
            resource_rename(
                "src-skill",
                "dst-skill",
                base_dir=skills_dir,
                label="Skill",
                is_dir=True,
            )

        assert _snapshot_tree(skills_dir) == before

    def test_skill_rename_missing_dir_raises_resource_not_found(
        self, vaultspec: Path
    ) -> None:
        skills_dir = vaultspec / "rules" / "skills"
        with pytest.raises(ResourceNotFoundError):
            resource_rename(
                "no-skill", "x", base_dir=skills_dir, label="Skill", is_dir=True
            )

    def test_skill_rename_missing_skill_md_raises_resource_not_found(
        self, vaultspec: Path
    ) -> None:
        skills_dir = vaultspec / "rules" / "skills"
        (skills_dir / "hollow").mkdir()
        with pytest.raises(ResourceNotFoundError):
            resource_rename(
                "hollow", "x", base_dir=skills_dir, label="Skill", is_dir=True
            )


class TestRollback:
    def test_flat_rename_rolls_back_on_content_write_failure(
        self, vaultspec: Path
    ) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        _write_rule(rules_dir, "atomic-rule", body="Keep me intact.\n")
        before = _snapshot_tree(rules_dir)

        # Plant a directory exactly where ``atomic_write`` places its temp file
        # for the post-rename content write, so the write fails AFTER the rename
        # has already landed - forcing the reverse journal to undo real work.
        # The temp-name formula mirrors ``core.helpers.atomic_write``.
        new_path = rules_dir / "renamed-rule.md"
        obstacle = new_path.with_suffix(new_path.suffix + f".{os.getpid()}.tmp")
        obstacle.mkdir()

        with pytest.raises((VaultSpecError, OSError)):
            resource_rename(
                "atomic-rule", "renamed-rule", base_dir=rules_dir, label="Rule"
            )

        shutil.rmtree(obstacle)
        assert _snapshot_tree(rules_dir) == before

    def test_skill_rename_rolls_back_on_content_write_failure(
        self, vaultspec: Path
    ) -> None:
        skills_dir = vaultspec / "rules" / "skills"
        old_dir = _write_skill(skills_dir, "tx-skill", body="Skill stays whole.\n")
        (old_dir / "extra.md").write_text("extra resource\n", encoding="utf-8")
        before = _snapshot_tree(skills_dir)

        # The temp file rides the directory rename into the new skill dir, so the
        # SKILL.md content write fails only after the directory rename has landed.
        skill_md = old_dir / "SKILL.md"
        obstacle = skill_md.with_suffix(skill_md.suffix + f".{os.getpid()}.tmp")
        obstacle.mkdir()

        with pytest.raises((VaultSpecError, OSError)):
            resource_rename(
                "tx-skill",
                "renamed-skill",
                base_dir=skills_dir,
                label="Skill",
                is_dir=True,
            )

        # The obstacle was undone back into the old skill dir by the rollback.
        leftover = old_dir / f"SKILL.md.{os.getpid()}.tmp"
        if leftover.exists():
            shutil.rmtree(leftover)
        assert _snapshot_tree(skills_dir) == before


class TestContainment:
    def test_escaping_destination_refused(self, vaultspec: Path) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        _write_rule(rules_dir, "safe-rule")
        before = _snapshot_tree(rules_dir)

        with pytest.raises(VaultSpecError):
            resource_rename("safe-rule", "../escaped", base_dir=rules_dir, label="Rule")

        assert _snapshot_tree(rules_dir) == before

    def test_escaping_source_refused(self, vaultspec: Path) -> None:
        rules_dir = vaultspec / "rules" / "rules"
        with pytest.raises(VaultSpecError):
            resource_rename(
                "../../outside", "whatever", base_dir=rules_dir, label="Rule"
            )
