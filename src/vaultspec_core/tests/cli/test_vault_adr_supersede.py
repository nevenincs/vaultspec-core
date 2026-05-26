"""Integration tests for vault adr supersede CLI command."""

from __future__ import annotations

import json

import pytest

from vaultspec_core.cli import app
from vaultspec_core.core.types import init_paths

pytestmark = [pytest.mark.integration]

_OLD_ADR_CONTENT = (
    "---\ntags:\n  - '#adr'\n  - '#test-feat'\n"
    "date: '2026-05-17'\nrelated: []\n---\n"
    "# `test-feat` adr: `Old ADR` | (**status:** `accepted`)\n"
)
_NEW_ADR_CONTENT_17 = (
    "---\ntags:\n  - '#adr'\n  - '#test-feat'\n"
    "date: '2026-05-17'\nrelated: []\n---\n"
    "# `test-feat` adr: `New ADR` | (**status:** `proposed`)\n"
)
_NEW_ADR_CONTENT_20 = (
    "---\ntags:\n  - '#adr'\n  - '#test-feat'\n"
    "date: '2026-05-20'\nrelated: []\n---\n"
    "# `test-feat` adr: `New ADR` | (**status:** `proposed`)\n"
)


@pytest.fixture
def test_project(tmp_path):
    """Setup a simplified project structure for adr supersede tests."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create required directory structure
    (project_dir / ".vault" / "adr").mkdir(parents=True, exist_ok=True)
    (project_dir / ".vaultspec").mkdir(parents=True, exist_ok=True)

    from vaultspec_core.config.workspace import resolve_workspace

    layout = resolve_workspace(target_override=project_dir)
    init_paths(layout)

    return project_dir


def test_adr_supersede_missing_old_fails(runner, test_project):
    # Setup new ADR file only
    new_adr = test_project / ".vault" / "adr" / "2026-05-17-new-adr.md"
    new_adr.write_text(_NEW_ADR_CONTENT_17, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-non-existent-adr",
            "--by",
            "2026-05-17-new-adr",
        ],
    )
    assert result.exit_code == 1
    assert "Old ADR document" in result.output
    assert "not found" in result.output


def test_adr_supersede_missing_new_fails(runner, test_project):
    # Setup old ADR file only
    old_adr = test_project / ".vault" / "adr" / "2026-05-17-old-adr.md"
    old_adr.write_text(_OLD_ADR_CONTENT, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-old-adr",
            "--by",
            "2026-05-17-non-existent-adr",
        ],
    )
    assert result.exit_code == 1
    assert "New ADR document" in result.output
    assert "not found" in result.output


def test_adr_supersede_missing_by_option_fails(runner, test_project):
    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-old-adr",
        ],
    )
    assert result.exit_code == 1
    assert "--by option is required" in result.output


def test_adr_supersede_success_mutates_both_files(runner, test_project):
    # Setup old ADR with \r\n line endings and custom field
    old_content = (
        "---\r\n"
        "tags:\r\n"
        "  - '#adr'\r\n"
        "  - '#test-feat'\r\n"
        "date: '2026-05-17'\r\n"
        "related: []\r\n"
        "custom_field: 'hello'\r\n"
        "---\r\n"
        "# `test-feat` adr: `Old ADR Title` | (**status:** `accepted`)\r\n"
        "\r\n"
        "Body content here\r\n"
    )
    old_adr = test_project / ".vault" / "adr" / "2026-05-17-old-adr.md"
    old_adr.write_bytes(old_content.encode("utf-8"))

    # Setup new ADR with \n line endings and custom field
    new_content = (
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#test-feat'\n"
        "date: '2026-05-20'\n"
        "related: []\n"
        "other_field: 'world'\n"
        "---\n"
        "# `test-feat` adr: `New ADR Title` | (**status:** `proposed`)\n"
        "\n"
        "New body content here\n"
    )
    new_adr = test_project / ".vault" / "adr" / "2026-05-20-new-adr.md"
    new_adr.write_bytes(new_content.encode("utf-8"))

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-old-adr",
            "--by",
            "2026-05-20-new-adr",
        ],
    )
    assert result.exit_code == 0

    # Check old ADR mutations
    mutated_old = old_adr.read_bytes().decode("utf-8")
    assert "\r\n" in mutated_old  # line ending preserved
    assert "superseded_by: '2026-05-20-new-adr'" in mutated_old
    assert "custom_field: 'hello'" in mutated_old  # preserved unknown field
    assert (
        "# `test-feat` adr: `Old ADR Title` | (**status:** `superseded`)" in mutated_old
    )

    # Check new ADR mutations
    mutated_new = new_adr.read_bytes().decode("utf-8")
    assert "\r\n" not in mutated_new  # line ending preserved
    assert "supersedes:\n  - '2026-05-17-old-adr'" in mutated_new
    assert "other_field: 'world'" in mutated_new  # preserved unknown field


def test_adr_supersede_dry_run(runner, test_project):
    old_adr = test_project / ".vault" / "adr" / "2026-05-17-old-adr.md"
    old_adr.write_text(_OLD_ADR_CONTENT, encoding="utf-8")
    new_adr = test_project / ".vault" / "adr" / "2026-05-20-new-adr.md"
    new_adr.write_text(_NEW_ADR_CONTENT_20, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-old-adr",
            "--by",
            "2026-05-20-new-adr",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would supersede ADR:" in result.output

    # Check files are NOT created or mutated
    old_content = old_adr.read_text(encoding="utf-8")
    assert "superseded_by:" not in old_content
    assert "superseded" not in old_content

    new_content = new_adr.read_text(encoding="utf-8")
    assert "supersedes:" not in new_content


def test_adr_supersede_json_output(runner, test_project):
    old_adr = test_project / ".vault" / "adr" / "2026-05-17-old-adr.md"
    old_adr.write_text(_OLD_ADR_CONTENT, encoding="utf-8")
    new_adr = test_project / ".vault" / "adr" / "2026-05-20-new-adr.md"
    new_adr.write_text(_NEW_ADR_CONTENT_20, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "adr",
            "supersede",
            "2026-05-17-old-adr",
            "--by",
            "2026-05-20-new-adr",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema"] == "vaultspec.vault.adr.supersede.v1"
    assert payload["status"] == "updated"
    assert "2026-05-17-old-adr.md" in payload["data"]["old_path"]
    assert "2026-05-20-new-adr.md" in payload["data"]["new_path"]
