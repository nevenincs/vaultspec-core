"""Integration tests for vault rule promote CLI command and rule migration."""

from __future__ import annotations

import json

import pytest

from vaultspec_core.cli import app
from vaultspec_core.core.rules import rules_list
from vaultspec_core.core.types import init_paths

pytestmark = [pytest.mark.integration]


@pytest.fixture
def test_project(tmp_path):
    """Setup a simplified project structure for rule promotion tests."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create required directory structure
    (project_dir / ".vault" / "audit").mkdir(parents=True, exist_ok=True)
    (project_dir / ".vaultspec" / "rules" / "rules").mkdir(parents=True, exist_ok=True)

    from vaultspec_core.config.workspace import resolve_workspace

    layout = resolve_workspace(target_override=project_dir)
    init_paths(layout)

    return project_dir


def test_rule_promote_missing_audit_fails(runner, test_project):
    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "non-existent-audit",
            "--as",
            "some-rule",
        ],
    )
    assert result.exit_code == 1
    assert "Audit document" in result.output
    assert "not found" in result.output


def test_rule_promote_invalid_kebab_fails(runner, test_project):
    # Setup audit file first
    audit_file = test_project / ".vault" / "audit" / "2026-05-17-test-audit.md"
    audit_file.write_text(
        "---\ntags:\n  - '#audit'\n  - '#test-feat'\n"
        "date: '2026-05-17'\nrelated: []\n---\n# Audit\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "InvalidRuleName",
        ],
    )
    assert result.exit_code == 1
    assert "must be in kebab-case" in result.output


def test_rule_promote_existing_rule_fails_unless_forced(runner, test_project):
    # Setup audit file
    audit_file = test_project / ".vault" / "audit" / "2026-05-17-test-audit.md"
    audit_file.write_text(
        "---\ntags:\n  - '#audit'\n  - '#test-feat'\n"
        "date: '2026-05-17'\nrelated: []\n---\n# Audit\n",
        encoding="utf-8",
    )

    # Create the rule file beforehand (flat under the rules root).
    rule_dir = test_project / ".vaultspec" / "rules" / "rules"
    rule_dir.mkdir(parents=True, exist_ok=True)
    rule_file = rule_dir / "my-rule.md"
    rule_file.write_text("# Existing Rule", encoding="utf-8")

    # Try to promote without --force
    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "my-rule",
        ],
    )
    assert result.exit_code == 1
    assert "already exists" in result.output

    # Try to promote with --force
    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "my-rule",
            "--force",
        ],
    )
    assert result.exit_code == 0
    assert "Rule promoted successfully" in result.output


def test_rule_promote_success_mutates_audit_and_creates_rule(runner, test_project):
    # Setup audit file with \r\n line endings to check preservation
    audit_content = (
        "---\r\n"
        "tags:\r\n"
        "  - '#audit'\r\n"
        "  - '#test-feat'\r\n"
        "date: '2026-05-17'\r\n"
        "related: []\r\n"
        "custom_field: 'hello'\r\n"
        "---\r\n"
        "# Audit Content\r\n"
    )
    audit_file = test_project / ".vault" / "audit" / "2026-05-17-test-audit.md"
    audit_file.write_bytes(audit_content.encode("utf-8"))

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "promoted-rule",
        ],
    )
    assert result.exit_code == 0

    # Check rule file exists flat under the rules root (no project/ subdir).
    rule_file = test_project / ".vaultspec" / "rules" / "rules" / "promoted-rule.md"
    assert rule_file.exists()
    assert not (test_project / ".vaultspec" / "rules" / "rules" / "project").exists()
    rule_content = rule_file.read_text(encoding="utf-8")
    assert 'derived_from:\n  - "audit:2026-05-17-test-audit"' in rule_content
    assert "# Rule" in rule_content
    assert "## Why" in rule_content
    assert "## How" in rule_content

    # Check audit file is mutated properly
    mutated_audit = audit_file.read_bytes().decode("utf-8")
    assert "\r\n" in mutated_audit  # line ending preserved
    assert "promoted_to:" in mutated_audit
    assert "rule:promoted-rule" in mutated_audit
    assert "custom_field: 'hello'" in mutated_audit  # preserved unknown field


def test_rule_promote_dry_run(runner, test_project):
    audit_file = test_project / ".vault" / "audit" / "2026-05-17-test-audit.md"
    audit_file.write_text(
        "---\ntags:\n  - '#audit'\n  - '#test-feat'\n"
        "date: '2026-05-17'\nrelated: []\n---\n# Audit\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "dry-run-rule",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would promote rule:" in result.output

    # Check files are NOT created or mutated
    rule_file = test_project / ".vaultspec" / "rules" / "rules" / "dry-run-rule.md"
    assert not rule_file.exists()

    audit_content = audit_file.read_text(encoding="utf-8")
    assert "promoted_to:" not in audit_content


def test_rule_promote_json_output(runner, test_project):
    audit_file = test_project / ".vault" / "audit" / "2026-05-17-test-audit.md"
    audit_file.write_text(
        "---\ntags:\n  - '#audit'\n  - '#test-feat'\n"
        "date: '2026-05-17'\nrelated: []\n---\n# Audit\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--target",
            str(test_project),
            "vault",
            "rule",
            "promote",
            "--from",
            "2026-05-17-test-audit",
            "--as",
            "json-rule",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema"] == "vaultspec.vault.rule.promote.v1"
    assert payload["status"] == "created"
    assert "json-rule.md" in payload["data"]["path"]


def test_nested_custom_rules_are_flattened(runner, test_project):
    """A custom rule under the legacy project/ subdir is sanitized to flat.

    Nested rule folders are not supported; rules_list() (and sync) run the
    sanitizer, which flattens any nested custom rule up to the rules root,
    removes the emptied subdir, and never touches builtins.
    """
    rules_dir = test_project / ".vaultspec" / "rules" / "rules"

    # A custom rule authored under the legacy project/ subdir (nested).
    nested_rule_file = rules_dir / "project" / "nested-custom-rule.md"
    nested_rule_file.parent.mkdir(parents=True, exist_ok=True)
    nested_rule_file.write_text("# Nested Custom Rule", encoding="utf-8")

    # A builtin rule sits flat in the same folder.
    builtin_rule_file = rules_dir / "some-builtin.builtin.md"
    builtin_rule_file.write_text("# Builtin Rule", encoding="utf-8")

    assert nested_rule_file.exists()
    assert builtin_rule_file.exists()

    # rules_list() triggers the sanitizer (flatten_nested_custom_rules).
    rules = rules_list()

    # 1. The nested custom rule is flattened to the rules root and the empty
    #    project/ subdir is removed.
    flattened = rules_dir / "nested-custom-rule.md"
    assert flattened.exists()
    assert not nested_rule_file.exists()
    assert not (rules_dir / "project").exists()

    # 2. The builtin is untouched.
    assert builtin_rule_file.exists()

    # 3. rules_list reports the flat custom rule name (no project/ prefix).
    names = [r["name"] for r in rules]
    assert "nested-custom-rule.md" in names
    assert "some-builtin.builtin.md" in names
    assert not any(n.startswith("project/") for n in names)
