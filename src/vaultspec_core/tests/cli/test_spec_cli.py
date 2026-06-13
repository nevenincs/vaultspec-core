"""Tests for the spec command group (spec rules, spec skills, etc.).

Covers: help text for resource groups, functional tests (rules list, hooks list),
and direct handler dispatch routing.
"""

from typing import ClassVar

import pytest

from vaultspec_core.cli import app

from .conftest import setup_rules_dir

pytestmark = [pytest.mark.unit]


class TestSpecCliHelp:
    """Verify --help text for resource groups under the spec namespace."""

    def test_main_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "--help"]
        )
        assert result.exit_code == 0
        for resource in [
            "rules",
            "skills",
            "system",
            "hooks",
            "mcps",
        ]:
            assert resource in result.output, f"Missing '{resource}' in help output"

    def test_mcps_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "mcps", "--help"]
        )
        assert result.exit_code == 0
        for cmd in ["list", "status", "add", "remove", "sync"]:
            assert cmd in result.output, f"Missing '{cmd}' in MCP help"

    def test_rules_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "rules", "--help"]
        )
        assert result.exit_code == 0
        for cmd in ["list", "add", "show", "edit", "remove", "rename", "sync"]:
            assert cmd in result.output, f"Missing '{cmd}' in rules help"

    def test_skills_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "skills", "--help"]
        )
        assert result.exit_code == 0

    def test_system_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "system", "--help"]
        )
        assert result.exit_code == 0
        for cmd in ["show", "sync"]:
            assert cmd in result.output, f"Missing '{cmd}' in system help"

    def test_hooks_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "hooks", "--help"]
        )
        assert result.exit_code == 0
        for cmd in ["list", "run"]:
            assert cmd in result.output, f"Missing '{cmd}' in hooks help"


class TestSpecCliFunctional:
    """Functional tests exercising real CLI commands under spec namespace."""

    pytestmark: ClassVar = [pytest.mark.integration]

    def test_rules_list_output(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "rules", "list"]
        )
        assert result.exit_code == 0

    def test_hooks_list_empty(self, runner, tmp_path):
        (tmp_path / ".vaultspec").mkdir()
        result = runner.invoke(
            app, ["--target", str(tmp_path), "spec", "hooks", "list"]
        )
        assert result.exit_code == 0

    def test_rules_add_json_error_is_parseable_envelope(
        self, runner, synthetic_project
    ):
        """A spec failure under --json must be a parseable error
        envelope, not a plain-text line a JSON consumer cannot read."""
        import json

        runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "add",
                "dup-rule",
                "--body",
                "first",
            ],
        )
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "add",
                "dup-rule",
                "--body",
                "second",
                "--json",
            ],
        )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["schema"] == "vaultspec.error.v1"
        assert payload["status"] == "failed"
        assert payload["data"]["message"]


class TestSpecCliDispatchRouting:
    """Test that core handlers can be called directly."""

    def test_rules_list_handler(self, synthetic_project):
        from ...core import rules_list

        rules_list()

    def test_rules_add_handler(self, tmp_path):
        from ...core import init_paths, rules_add
        from ...core import types as _t

        setup_rules_dir(tmp_path)
        init_paths(tmp_path)

        rules_add(
            name="test-rule",
            content="Test content for rule.",
            force=False,
        )

        # Custom rules are authored flat under the rules root; no nested
        # ``project/`` subdir is created.
        rule_file = _t.get_context().rules_src_dir / "test-rule.md"
        assert rule_file.exists()
        assert not (_t.get_context().rules_src_dir / "project").exists()
        content = rule_file.read_text(encoding="utf-8")
        assert "test-rule" in content

    def test_rules_add_sanitizes_nested_name(self, tmp_path):
        """A nested or project-prefixed rule name is sanitized to a flat file."""
        from ...core import init_paths, rules_add
        from ...core import types as _t

        setup_rules_dir(tmp_path)
        init_paths(tmp_path)

        # A legacy ``project/`` prefix and a deeper nested path both collapse to
        # the basename: nested rule folders are never created.
        rules_add(name="project/legacy-rule", content="Body.", force=False)
        rules_add(name="sub/deep-rule", content="Body.", force=False)

        rules_src = _t.get_context().rules_src_dir
        assert (rules_src / "legacy-rule.md").exists()
        assert (rules_src / "deep-rule.md").exists()
        assert not (rules_src / "project").exists()
        assert not (rules_src / "sub").exists()
        # The sanitized stem (not the nested path) is written into frontmatter.
        assert "name: legacy-rule" in (rules_src / "legacy-rule.md").read_text(
            encoding="utf-8"
        )
