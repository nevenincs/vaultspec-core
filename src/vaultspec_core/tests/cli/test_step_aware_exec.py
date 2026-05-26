"""Integration tests for step-aware execution record scaffolding and status hinting.

Covers mutual exclusion, individual step routing and hydration, legacy fallback
deprecation warning, bulk scaffolding (idempotency, force, outcomes rendering),
and plan status exec-missing warning hinting.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vaultspec_core.cli import app

pytestmark = [pytest.mark.integration]


def setup_test_plan(project_dir: Path) -> Path:
    """Helper to write a clean test plan file with specific checked steps."""
    # Write the required prerequisite ADR document first
    adr_dir = project_dir / ".vault" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr_file = adr_dir / "2026-05-17-test-feature-adr.md"
    adr_file.write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#test-feature'\n"
        "date: '2026-05-17'\n"
        "---\n"
        "\n"
        "# `test-feature` adr: Architectural Decision\n",
        encoding="utf-8",
    )

    plan_dir = project_dir / ".vault" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "2026-05-17-test-feature-plan.md"
    plan_file.write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#test-feature'\n"
        "date: '2026-05-17'\n"
        "tier: L2\n"
        "---\n"
        "\n"
        "# `test-feature` plan\n"
        "\n"
        "## Phase `P01` - Test Phase\n"
        "- [x] `P01.S01` - First step; `src/foo.py`.\n"
        "- [x] `P01.S02` - Second step; `src/bar.py`.\n"
        "- [ ] `P01.S03` - Third step; `src/baz.py`.\n",
        encoding="utf-8",
    )
    return plan_file


def test_step_aware_mutual_exclusion(runner, synthetic_project):
    """Passing both options, or options with wrong types, must fail."""
    # Both options supplied on exec
    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--step",
            "P01.S01",
            "--all-steps",
        ],
    )
    assert result.exit_code != 0
    assert (
        "Error: --step and --all-steps options are mutually exclusive." in result.output
    )

    # Supplied on wrong type (adr)
    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "adr",
            "--feature",
            "test-feature",
            "--step",
            "P01.S01",
        ],
    )
    assert result.exit_code != 0
    assert (
        "Error: --step and --all-steps options are only valid when creating 'exec' "
        "documents." in result.output
    )


def test_step_aware_legacy_fallback_warning(runner, synthetic_project):
    """Omitting flags displays warning and falls back to flat scaffolding."""
    setup_test_plan(synthetic_project)

    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--title",
            "Legacy Record",
        ],
    )
    assert result.exit_code == 0
    assert "Deprecation Warning:" in result.output

    # Verify a flat legacy execution file was created
    legacy_files = list(
        (synthetic_project / ".vault" / "exec").glob("*-test-feature-exec.md")
    )
    assert len(legacy_files) == 1
    content = legacy_files[0].read_text(encoding="utf-8")
    assert "Legacy Record" in content or "test-feature" in content


def test_step_aware_individual_scaffolding(runner, synthetic_project):
    """Individual step scaffolding custom routes and hydrates placeholders."""
    setup_test_plan(synthetic_project)

    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--step",
            "P01.S01",
        ],
    )
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify customized path routing
    target_file = (
        synthetic_project
        / ".vault"
        / "exec"
        / "2026-05-17-test-feature"
        / "2026-05-17-test-feature-P01-S01.md"
    )
    assert target_file.exists()

    content = target_file.read_text(encoding="utf-8")

    # Frontmatter assertions
    assert "step_id: 'S01'" in content
    assert "related:" in content
    assert '- "[[2026-05-17-test-feature-plan]]"' in content
    assert "tags:" in content
    assert "- '#exec'" in content
    assert "- '#test-feature'" in content

    # Hydrated body structure assertions
    assert "# First step" in content
    assert "## Scope" in content
    assert "- `src/foo.py`" in content
    assert "## Description" in content
    assert "## Outcome" in content
    assert "## Notes" in content


def test_step_aware_bulk_scaffolding(runner, synthetic_project):
    """Bulk scaffolding creates all records idempotently and obeys --force."""
    setup_test_plan(synthetic_project)

    # 1. First bulk generation run (should create all steps)
    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--all-steps",
        ],
    )
    assert result.exit_code == 0
    assert "created" in result.output
    assert "2026-05-17-test-feature-P01-S01.md" in result.output
    assert "2026-05-17-test-feature-P01-S02.md" in result.output
    assert "2026-05-17-test-feature-P01-S03.md" in result.output

    # Check files exist
    base_dir = synthetic_project / ".vault" / "exec" / "2026-05-17-test-feature"
    file_s1 = base_dir / "2026-05-17-test-feature-P01-S01.md"
    file_s2 = base_dir / "2026-05-17-test-feature-P01-S02.md"
    file_s3 = base_dir / "2026-05-17-test-feature-P01-S03.md"
    assert file_s1.exists()
    assert file_s2.exists()
    assert file_s3.exists()

    # 2. Second run (idempotency - existing files must be skipped)
    result2 = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--all-steps",
        ],
    )
    assert result2.exit_code == 0
    assert "skipped" in result2.output
    assert "skipped; exists" in result2.output

    # 3. Third run with --force (overwriting)
    result3 = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--all-steps",
            "--force",
        ],
    )
    assert result3.exit_code == 0
    assert "updated" in result3.output


def test_step_aware_bulk_scaffolding_json(runner, synthetic_project):
    """Bulk scaffolding with --json outputs the outcome in envelope schema."""
    setup_test_plan(synthetic_project)

    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--all-steps",
            "--json",
        ],
    )
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["status"] == "created"
    assert data["schema"] == "vaultspec.vault.add.v1"
    assert isinstance(data["data"]["items"], list)
    assert len(data["data"]["items"]) == 3
    assert data["data"]["items"][0]["outcome"] == "created"


def test_step_aware_status_hinting(runner, synthetic_project):
    """Plan status reports exec-missing warning and disappears when resolved."""
    setup_test_plan(synthetic_project)

    plan_path = str(
        synthetic_project / ".vault" / "plan" / "2026-05-17-test-feature-plan.md"
    )

    # 1. Run status when no exec files exist (S01, S02 are checked, should warn)
    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "plan",
            "status",
            plan_path,
        ],
    )
    assert result.exit_code == 0
    assert "! exec-missing" in result.output
    assert "S01" in result.output
    assert "S02" in result.output

    # Verify JSON envelope status format
    result_json = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "plan",
            "status",
            plan_path,
            "--json",
        ],
    )
    assert result_json.exit_code == 0
    data = json.loads(result_json.output)
    assert "exec_missing_ids" in data["data"]
    assert set(data["data"]["exec_missing_ids"]) == {"S01", "S02"}

    # 2. Scaffold execution record for S01
    runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "add",
            "exec",
            "--feature",
            "test-feature",
            "--step",
            "P01.S01",
        ],
    )

    # 3. Run status again (only S02 should remain missing)
    result2 = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "plan",
            "status",
            plan_path,
        ],
    )
    assert result2.exit_code == 0
    assert "S01" not in result2.output
    assert "S02" in result2.output
