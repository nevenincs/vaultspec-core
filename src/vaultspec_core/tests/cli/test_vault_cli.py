"""Unit tests for the vault command group.

Covers vault add, vault stats, vault check, etc.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app

from ...vaultcore import DocType

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


class TestGetVersion:
    """Verify version information is correctly retrieved."""

    def test_reads_version_from_pyproject(self, synthetic_project):
        from importlib.metadata import version

        from vaultspec_core.cli_common import get_version

        v = get_version()
        expected = version("vaultspec-core")
        assert v == expected

    def test_get_version_returns_string(self, synthetic_project):
        from vaultspec_core.cli_common import get_version

        assert isinstance(get_version(), str)


class TestHelpText:
    """Verify that --help output contains expected strings."""

    def test_main_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "vault", "--help"]
        )
        assert result.exit_code == 0
        assert "add" in result.output
        assert "check" in result.output
        assert "stats" in result.output

    def test_add_help(self, runner, synthetic_project):
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "vault", "add", "--help"]
        )
        assert result.exit_code == 0
        assert "--feature" in result.output


class TestAddSubcommand:
    """Verify 'vault add' behavior."""

    def test_add_generates_correct_filename(self, runner, synthetic_project):
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Cleanup potential leftover from previous failed tests
        expected_path = (
            synthetic_project / ".vault" / "adr" / f"{date_str}-test-feat-adr.md"
        )
        if expected_path.exists():
            expected_path.unlink()

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "adr",
                "--feature",
                "test-feat",
                "--title",
                "My Title",
            ],
        )
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert expected_path.exists()

    def test_add_strips_hash_from_feature(self, runner, synthetic_project):
        """Creating with #feature should strip the hash."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        expected_path = (
            synthetic_project / ".vault" / "adr" / f"{date_str}-my-feat-adr.md"
        )
        if expected_path.exists():
            expected_path.unlink()

        runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "adr",
                "--feature",
                "#my-feat",
            ],
        )
        assert expected_path.exists()

    def test_add_valid_doc_types_accepted(
        self, runner, tmp_path: Path, synthetic_project
    ):
        """Test all user-creatable DocType choices are accepted.

        ``DocType.INDEX`` is auto-generated and not user-creatable; the
        ``vault add`` surface rejects it with an explicit error so this
        test exercises only the authored types.

        Uses real templates via seed_builtins - never shadow template files.
        """
        from vaultspec_core.builtins import seed_builtins
        from vaultspec_core.core.types import init_paths

        # Seed real templates from the repo into the tmp workspace
        rules_dir = tmp_path / ".vaultspec"
        rules_dir.mkdir(parents=True)
        seed_builtins(rules_dir, force=True)

        # Create vault type directories
        for dt in DocType:
            (tmp_path / ".vault" / dt.value).mkdir(parents=True, exist_ok=True)

        # Create prerequisite docs for feature 'f' so exec validation passes.
        # Exec requires research + ADR + plan to exist for the feature.
        for prereq in ("research", "adr", "plan"):
            d = tmp_path / ".vault" / prereq
            (d / f"2026-01-01-f-{prereq}.md").write_text(
                f"---\ntags:\n  - '#{prereq}'\n  - '#f'\n"
                f"date: '2026-01-01'\nrelated: []\n---\n# Prerequisite\n",
                encoding="utf-8",
            )

        init_paths(tmp_path)

        for dt in DocType:
            if dt is DocType.INDEX:
                continue
            result = runner.invoke(
                app,
                [
                    "--target",
                    str(tmp_path),
                    "vault",
                    "add",
                    dt.value,
                    "--feature",
                    "f",
                ],
            )
            assert result.exit_code == 0, (
                f"DocType {dt.value} rejected (output: {result.output})"
            )

    def test_add_index_type_is_rejected(
        self, runner, tmp_path: Path, synthetic_project
    ):
        """``vault add index`` must redirect users to ``vault feature index``.

        Index files are auto-generated; allowing ``vault add`` to write
        one would put the file at the wrong filename
        (``<date>-<feature>-index.md`` instead of
        ``<feature>.index.md``) and bypass the generator's bookkeeping.
        """
        from vaultspec_core.builtins import seed_builtins
        from vaultspec_core.core.types import init_paths

        rules_dir = tmp_path / ".vaultspec"
        rules_dir.mkdir(parents=True)
        seed_builtins(rules_dir, force=True)
        for dt in DocType:
            (tmp_path / ".vault" / dt.value).mkdir(parents=True, exist_ok=True)
        init_paths(tmp_path)

        result = runner.invoke(
            app,
            [
                "--target",
                str(tmp_path),
                "vault",
                "add",
                "index",
                "--feature",
                "rejected-feature",
            ],
        )
        assert result.exit_code != 0
        assert "auto-generated" in result.output
        assert "vault feature index" in result.output
        # No .vault/index/<...>.md file should have been written.
        index_dir = tmp_path / ".vault" / "index"
        if index_dir.is_dir():
            assert not any(index_dir.iterdir())

    def test_add_created_doc_passes_validation(self, runner, synthetic_project):
        """Created documents must pass the project's own frontmatter validation."""
        from vaultspec_core.vaultcore.parser import parse_vault_metadata

        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        expected_path = (
            synthetic_project
            / ".vault"
            / "research"
            / f"{date_str}-valid-doc-research.md"
        )
        if expected_path.exists():
            expected_path.unlink()

        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "research",
                "--feature",
                "valid-doc",
                "--title",
                "Validation Test",
            ],
        )
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert expected_path.exists()

        # The created document must pass our own validation
        content = expected_path.read_text(encoding="utf-8")
        metadata, _ = parse_vault_metadata(content)
        errors = metadata.validate()
        assert not errors, f"Created document fails validation: {errors}"

    def test_add_retains_template_annotations_until_explicit_fix(
        self, runner, synthetic_project
    ):
        """Hydration must not strip agent-facing template instructions."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        expected_path = (
            synthetic_project
            / ".vault"
            / "research"
            / f"{date_str}-annotation-lifecycle-research.md"
        )
        if expected_path.exists():
            expected_path.unlink()

        add_result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "research",
                "--feature",
                "annotation-lifecycle",
                "--title",
                "Annotation Lifecycle",
            ],
        )
        assert add_result.exit_code == 0, add_result.output

        created = expected_path.read_text(encoding="utf-8")
        assert "<!-- FRONTMATTER RULES:" in created
        assert "<!-- LINK RULES:" in created

        fix_result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "check",
                "annotations",
                "--feature",
                "annotation-lifecycle",
                "--fix",
            ],
        )
        assert fix_result.exit_code == 0, fix_result.output

        sanitized = expected_path.read_text(encoding="utf-8")
        assert "<!-- FRONTMATTER RULES:" not in sanitized
        assert "<!-- LINK RULES:" not in sanitized


class TestVaultJsonOutput:
    """JSON-mode commands must produce machine-readable stdout only."""

    def test_add_dry_run_json_has_no_human_prefix(self, runner, synthetic_project):
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "add",
                "research",
                "--feature",
                "json-dry-run",
                "--dry-run",
                "--json",
            ],
        )

        payload = json.loads(result.output)["data"]
        assert result.exit_code == 0, result.output
        assert result.output.lstrip().startswith("{")
        assert payload["dry_run"] is True
        assert payload["type"] == "research"

    def test_graph_empty_json_has_no_human_prefix(self, factory):
        factory.install("core")

        result = factory.run("vault", "graph", "--json")

        payload = json.loads(result.output)["data"]
        assert result.exit_code == 0, result.output
        assert result.output.lstrip().startswith("{")
        assert payload["nodes"] == []
        assert payload.get("links", payload.get("edges", [])) == []

    def test_feature_index_empty_json_has_no_human_prefix(self, factory):
        factory.install("core")

        result = factory.run("vault", "feature", "index", "--json")

        payload = json.loads(result.output)["data"]
        assert result.exit_code == 0, result.output
        assert result.output.lstrip().startswith("{")
        assert payload == {"generated": []}


class TestVaultGraphScopingFlags:
    """vault graph --node/--depth ego scoping and --derived/--no-derived."""

    def _graph_json(self, runner, project, *extra: str) -> dict:
        result = runner.invoke(
            app,
            ["--target", str(project), "vault", "graph", "--json", *extra],
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    def _busiest_node(self, payload: dict) -> str:
        """Return the node id with the most incoming plus outgoing links."""
        nodes = payload["data"]["nodes"]
        ranked = sorted(
            nodes,
            key=lambda n: (len(n["out_links"]) + len(n["in_links"]), n["id"]),
            reverse=True,
        )
        return ranked[0]["id"]

    def test_full_graph_includes_derived_edges_by_default(
        self, runner, synthetic_project
    ):
        payload = self._graph_json(runner, synthetic_project)
        assert payload["schema"] == "vaultspec.vault.graph.v2"
        data = payload["data"]
        assert "derived_edges" in data
        assert "edges" in data
        # derived_edges is a distinct array, never folded into edges.
        assert isinstance(data["derived_edges"], list)
        assert len(data["derived_edges"]) > 0

    def test_no_derived_empties_the_derived_array(self, runner, synthetic_project):
        payload = self._graph_json(runner, synthetic_project, "--no-derived")
        assert payload["data"]["derived_edges"] == []
        # The canonical edges array is unaffected by the derived toggle.
        with_derived = self._graph_json(runner, synthetic_project)
        assert payload["data"]["edges"] == with_derived["data"]["edges"]

    def test_node_scopes_to_ego_neighbourhood(self, runner, synthetic_project):
        full = self._graph_json(runner, synthetic_project)
        centre = self._busiest_node(full)
        ego = self._graph_json(runner, synthetic_project, "--node", centre)
        ego_ids = {n["id"] for n in ego["data"]["nodes"]}
        assert centre in ego_ids
        # An ego scope is a subset of the full node set.
        full_ids = {n["id"] for n in full["data"]["nodes"]}
        assert ego_ids <= full_ids
        assert len(ego_ids) < len(full_ids)

    def test_depth_zero_returns_only_the_centre(self, runner, synthetic_project):
        full = self._graph_json(runner, synthetic_project)
        centre = self._busiest_node(full)
        ego0 = self._graph_json(
            runner, synthetic_project, "--node", centre, "--depth", "0"
        )
        ids = {n["id"] for n in ego0["data"]["nodes"]}
        assert ids == {centre}

    def test_depth_grows_neighbourhood_monotonically(self, runner, synthetic_project):
        full = self._graph_json(runner, synthetic_project)
        centre = self._busiest_node(full)
        n0 = len(
            self._graph_json(
                runner, synthetic_project, "--node", centre, "--depth", "0"
            )["data"]["nodes"]
        )
        n1 = len(
            self._graph_json(
                runner, synthetic_project, "--node", centre, "--depth", "1"
            )["data"]["nodes"]
        )
        assert n0 == 1
        assert n1 >= n0

    def test_missing_node_fails_with_exit_one(self, runner, synthetic_project):
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "vault",
                "graph",
                "--json",
                "--node",
                "this-node-does-not-exist",
            ],
        )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["status"] == "failed"
        assert "this-node-does-not-exist" in payload["data"]["message"]

    def test_ego_derived_edges_stay_within_scope(self, runner, synthetic_project):
        full = self._graph_json(runner, synthetic_project)
        centre = self._busiest_node(full)
        ego = self._graph_json(
            runner, synthetic_project, "--node", centre, "--depth", "2"
        )
        ids = {n["id"] for n in ego["data"]["nodes"]}
        for edge in ego["data"]["derived_edges"]:
            assert edge["source"] in ids
            assert edge["target"] in ids


class TestNoCommand:
    def test_no_command_prints_help(self, runner, synthetic_project):
        result = runner.invoke(app, ["--target", str(synthetic_project), "vault"])
        # vault_app uses no_args_is_help=True. The actual contract is that
        # help is rendered to output; the exit code is a Typer-version
        # implementation detail (0 in newer Typer, 2 in older), so we
        # assert on the rendered help block, not the exit code.
        assert "Usage" in result.output, (
            f"vault command without args did not render help: {result.output}"
        )
        assert "add" in result.output, (
            f"vault help did not list the 'add' subcommand: {result.output}"
        )
