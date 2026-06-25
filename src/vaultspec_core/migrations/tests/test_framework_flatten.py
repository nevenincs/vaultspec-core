"""Tests for the ``framework_flatten`` registry entry.

Exercises
:func:`vaultspec_core.migrations.m_0_1_35_framework_flatten.migrate`
against real on-disk fixtures. The migration relocates the resource
directories nested under ``.vaultspec/rules/`` up to ``.vaultspec/``,
resolving the wrapper/inner-``rules`` name collision through a temporary
name. All assertions are against the real filesystem; no mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.migrations import REGISTRY
from vaultspec_core.migrations.m_0_1_35_framework_flatten import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_RESOURCE_SUBDIRS = (
    "skills",
    "agents",
    "system",
    "templates",
    "hooks",
    "mcps",
    "reference",
)


@pytest.fixture(autouse=True)
def _reset_cfg():
    reset_config()
    yield
    reset_config()


def _nested_layout(vaultspec_dir: Path) -> None:
    """Build a pre-flatten ``.vaultspec/rules/<resource>`` wrapper tree."""
    wrapper = vaultspec_dir / "rules"

    inner = wrapper / "rules"
    inner.mkdir(parents=True)
    (inner / "vaultspec.builtin.md").write_text("rule body", encoding="utf-8")
    (inner / ".gitignore").write_text("*\n", encoding="utf-8")

    for name in _RESOURCE_SUBDIRS:
        d = wrapper / name
        d.mkdir(parents=True)
        (d / f"{name}.marker").write_text(name, encoding="utf-8")

    # A directory-style resource (skills) carries a nested entrypoint.
    skill = wrapper / "skills" / "vaultspec-adr"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("skill", encoding="utf-8")


class TestRelocatesNestedResources:
    def test_all_resource_dirs_move_up(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        _nested_layout(vs)

        result = migrate(tmp_path)

        # Inner rules content lands directly under .vaultspec/rules/.
        assert (vs / "rules" / "vaultspec.builtin.md").read_text(
            encoding="utf-8"
        ) == "rule body"
        assert (vs / "rules" / ".gitignore").exists()
        # No doubled rules path remains.
        assert not (vs / "rules" / "rules").exists()

        for name in _RESOURCE_SUBDIRS:
            assert (vs / name / f"{name}.marker").read_text(encoding="utf-8") == name
            assert not (vs / "rules" / name).exists()

        assert (vs / "skills" / "vaultspec-adr" / "SKILL.md").exists()

        # 7 non-rules dirs + the inner rules = 8 relocations.
        assert result.counts["relocated"] == 8
        assert result.counts["wrapper_removed"] == 1
        assert "flattened 8 resource directories" in result.summary

    def test_inner_rules_collision_resolved(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        wrapper = vs / "rules"
        inner = wrapper / "rules"
        inner.mkdir(parents=True)
        (inner / "vaultspec.builtin.md").write_text("body", encoding="utf-8")

        migrate(tmp_path)

        assert (vs / "rules").is_dir()
        assert (vs / "rules" / "vaultspec.builtin.md").read_text(
            encoding="utf-8"
        ) == "body"
        assert not (vs / "rules" / "rules").exists()


class TestIdempotence:
    def test_already_flat_is_noop(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        (vs / "rules").mkdir(parents=True)
        (vs / "rules" / "vaultspec.builtin.md").write_text("r", encoding="utf-8")
        (vs / "skills" / "vaultspec-adr").mkdir(parents=True)
        (vs / "skills" / "vaultspec-adr" / "SKILL.md").write_text("s", encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts["relocated"] == 0
        assert result.counts["wrapper_removed"] == 0
        assert "already flat" in result.summary
        # Flat layout is untouched.
        rule = vs / "rules" / "vaultspec.builtin.md"
        assert rule.read_text(encoding="utf-8") == "r"

    def test_second_run_is_noop(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        _nested_layout(vs)

        first = migrate(tmp_path)
        assert first.counts["relocated"] == 8

        second = migrate(tmp_path)
        assert second.counts["relocated"] == 0
        assert "already flat" in second.summary

    def test_no_vaultspec_dir_is_noop(self, tmp_path: Path):
        result = migrate(tmp_path)
        assert result.counts["relocated"] == 0
        assert "already flat" in result.summary


class TestPartialFailureRerun:
    def test_resumes_from_partial_state(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        # skills already relocated by a prior, interrupted run.
        (vs / "skills" / "vaultspec-adr").mkdir(parents=True)
        (vs / "skills" / "vaultspec-adr" / "SKILL.md").write_text("s", encoding="utf-8")
        # rules wrapper still holds the inner rules and agents.
        (vs / "rules" / "rules").mkdir(parents=True)
        (vs / "rules" / "rules" / "r.builtin.md").write_text("r", encoding="utf-8")
        (vs / "rules" / "agents").mkdir(parents=True)
        (vs / "rules" / "agents" / "a.md").write_text("a", encoding="utf-8")

        result = migrate(tmp_path)

        assert (vs / "skills" / "vaultspec-adr" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "s"
        assert (vs / "agents" / "a.md").read_text(encoding="utf-8") == "a"
        assert (vs / "rules" / "r.builtin.md").read_text(encoding="utf-8") == "r"
        assert not (vs / "rules" / "rules").exists()
        assert not (vs / "rules" / "agents").exists()
        assert result.counts["wrapper_removed"] == 1

    def test_merges_when_flat_destination_already_exists(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        # A prior partial run left an agents dir at the flat location.
        (vs / "agents").mkdir(parents=True)
        (vs / "agents" / "existing.md").write_text("existing", encoding="utf-8")
        # The wrapper still carries an agents dir with a new file.
        (vs / "rules" / "agents").mkdir(parents=True)
        (vs / "rules" / "agents" / "new.md").write_text("new", encoding="utf-8")
        (vs / "rules" / "rules").mkdir(parents=True)
        (vs / "rules" / "rules" / "r.builtin.md").write_text("r", encoding="utf-8")

        migrate(tmp_path)

        # Both the pre-existing and the relocated file survive the merge.
        assert (vs / "agents" / "existing.md").read_text(encoding="utf-8") == "existing"
        assert (vs / "agents" / "new.md").read_text(encoding="utf-8") == "new"
        assert not (vs / "rules" / "agents").exists()


class TestLeavesBookkeepingUntouched:
    def test_snapshots_and_manifest_survive(self, tmp_path: Path):
        vs = tmp_path / ".vaultspec"
        _nested_layout(vs)
        snap = vs / "_snapshots" / "rules" / "vaultspec.builtin.md"
        snap.parent.mkdir(parents=True)
        snap.write_text("snapshot", encoding="utf-8")
        manifest = vs / "providers.json"
        manifest.write_text("{}", encoding="utf-8")

        migrate(tmp_path)

        # Sibling bookkeeping is neither moved nor pulled into the flatten.
        assert snap.read_text(encoding="utf-8") == "snapshot"
        assert manifest.read_text(encoding="utf-8") == "{}"
        assert (vs / "_snapshots" / "rules" / "vaultspec.builtin.md").exists()


class TestRegistry:
    def test_registered_with_target_version(self):
        entry = next((m for m in REGISTRY if m.name == "framework_flatten"), None)
        assert entry is not None
        assert entry.target_version == "0.1.35"
