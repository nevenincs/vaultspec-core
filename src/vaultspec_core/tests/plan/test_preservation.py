"""Tests for plan-body preservation and dry-run/canonicalise CLI flags.

Covers:
1. Parse and round-trip preservation of unknown prose blocks.
2. CLI flag `--dry-run` printing unified diffs and avoiding writes.
3. CLI flag `--canonicalise` stripping unknown blocks.
4. Success output messages reporting correct preserved block count.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan

L1_SAMPLE = """---
tags:
  - '#plan'
  - '#demo-feature'
date: '2026-05-05'
tier: L1
related: []
---

General preamble (before title)

# `demo` plan

Prose description (before S01)

- [ ] `S01` - do work; `src/a.py`.

Some mid-step comment (before S02)

- [ ] `S02` - do more; `src/b.py`.

Final closing remarks (after all)
"""


@pytest.fixture()
def runner() -> CliRunner:
    """Typer test runner with colour disabled."""
    return CliRunner(env={"NO_COLOR": "1"})


def test_serialise_plan_preserves_unknown_blocks() -> None:
    """Verify that serialise_plan round-trips unknown blocks correctly."""
    plan_l1 = parse_plan(L1_SAMPLE)
    assert len(plan_l1.unknown_blocks) == 4
    serialized_l1 = serialise_plan(plan_l1, canonicalise=False)
    # The first serialization canonicalises the frontmatter and link rules block.
    # Subsequent parse-serialise loops should be perfectly identical (idempotent).
    re_parsed = parse_plan(serialized_l1)
    assert len(re_parsed.unknown_blocks) == 4
    assert serialise_plan(re_parsed, canonicalise=False) == serialized_l1


def test_serialise_plan_canonicalise_strips_unknown_blocks() -> None:
    """Verify that serialise_plan with canonicalise=True strips unknown blocks."""
    plan_l1 = parse_plan(L1_SAMPLE)
    serialized_l1 = serialise_plan(plan_l1, canonicalise=True)
    assert "General preamble" not in serialized_l1
    assert "Prose description" not in serialized_l1
    assert "Some mid-step comment" not in serialized_l1
    assert "Final closing remarks" not in serialized_l1


def test_cli_dry_run_does_not_modify_file(tmp_path, runner: CliRunner) -> None:
    """Verify that --dry-run outputs a unified diff and does not modify the file."""
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(L1_SAMPLE, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "check",
            str(plan_path),
            "S01",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout
    # Output should contain a unified diff showing S01 being checked
    assert "--- a/test-plan.md" in result.stdout
    assert "+++ b/test-plan.md" in result.stdout
    assert "-- [ ] `S01`" in result.stdout
    assert "+- [x] `S01`" in result.stdout

    # File should not be modified on disk
    assert plan_path.read_text(encoding="utf-8") == L1_SAMPLE


def test_cli_canonicalise_strips_and_reports_zero(tmp_path, runner: CliRunner) -> None:
    """Verify that --canonicalise strips unknown blocks and reports 0 preserved."""
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(L1_SAMPLE, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "check",
            str(plan_path),
            "S01",
            "--canonicalise",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "(Preserved 0 unknown blocks)" in result.stdout

    # File should be written and contain NO unknown blocks
    content = plan_path.read_text(encoding="utf-8")
    assert "General preamble" not in content
    assert "Prose description" not in content

    # S01 should be checked
    assert "- [x] `S01`" in content


def test_cli_standard_apply_preserves_and_reports_count(
    tmp_path, runner: CliRunner
) -> None:
    """Verify that standard apply preserves unknown blocks and reports count."""
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(L1_SAMPLE, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "check",
            str(plan_path),
            "S01",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "(Preserved 4 unknown blocks)" in result.stdout

    # File should be modified on disk
    content = plan_path.read_text(encoding="utf-8")
    assert "General preamble" in content
    assert "Prose description" in content
    assert "- [x] `S01`" in content


def test_cli_step_add_preservation(tmp_path, runner: CliRunner) -> None:
    """Verify step add maintains unknown blocks and prints proper message."""
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(L1_SAMPLE, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--action",
            "new step action",
            "--scope",
            "src/new.py",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Added Step `S03`." in result.stdout
    assert "(Preserved 4 unknown blocks)" in result.stdout

    content = plan_path.read_text(encoding="utf-8")
    assert "General preamble" in content
    assert "Prose description" in content
    assert "new step action" in content


def test_cli_epic_intent_edit_l4_preservation(tmp_path, runner: CliRunner) -> None:
    """Verify epic intent edit maintains unknown blocks in L4 plans."""
    l4_sample = """---
tags:
  - '#plan'
  - '#demo-feature'
date: '2026-05-05'
tier: L4
related: []
---

Preamble L4

# `L4 demo` plan

## Epic intent

Old epic intent paragraph.

- [ ] `W01.P01.S01` - action; `src/a.py`.

Closing text
"""
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(l4_sample, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "epic",
            "intent",
            "edit",
            str(plan_path),
            "--text",
            "New epic intent text mentioning PM.",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Edited Epic intent." in result.stdout
    assert "(Preserved 2 unknown blocks)" in result.stdout

    content = plan_path.read_text(encoding="utf-8")
    assert "Preamble L4" in content
    assert "Closing text" in content
    assert "New epic intent text mentioning PM." in content
