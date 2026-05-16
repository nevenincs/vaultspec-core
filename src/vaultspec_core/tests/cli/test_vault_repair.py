"""Tests for the ``vaultspec-core vault repair`` operator pipeline."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app
from vaultspec_core.cli.vault_cmd import _render_repair_run
from vaultspec_core.config import reset_config
from vaultspec_core.vaultcore.checks import run_all_checks
from vaultspec_core.vaultcore.repair import (
    RepairRun,
    _vault_file_fingerprints,
    run_repair_pipeline,
)

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.unit]


def _write_doc(
    root: Path,
    doc_type: str,
    stem: str,
    feature: str,
    *,
    docs_dir: str = ".vault",
) -> Path:
    path = root / docs_dir / doc_type / f"{stem}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "tags:\n"
        f"  - '#{doc_type}'\n"
        f"  - '#{feature}'\n"
        "date: '2026-05-15'\n"
        "related: []\n"
        "---\n"
        f"\n# {stem}\n",
        encoding="utf-8",
    )
    return path


def _json_payload(output: str) -> dict:
    assert output.lstrip().startswith("{"), (
        "JSON-mode CLI output must not include human text before the payload:\n"
        f"{output}"
    )
    return json.loads(output)


def _write_state_mutation_workspace(root: Path) -> None:
    """Create a tmp vault that requires multiple sequential file mutations."""
    research = root / ".vault" / "research" / "2026-05-15-State-Mutation-research.md"
    plan = root / ".vault" / "plan" / "2026-05-15-state-mutation-plan.md"
    adr = root / ".vault" / "adr" / "2026-05-15-state-mutation-adr.md"
    for path in (research, plan, adr):
        path.parent.mkdir(parents=True, exist_ok=True)

    research.write_text(
        "---\n"
        "tags:\n"
        "  - research\n"
        "  - state-mutation\n"
        "date: '2026-05-15'\n"
        "related: []\n"
        "---\n\n# Research\n",
        encoding="utf-8",
    )
    plan.write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#state-mutation'\n"
        "date: '2026-05-15'\n"
        "related:\n"
        "  - '[[2026-05-15-State-Mutation-research.md]]'\n"
        "  - '[[missing-target]]'\n"
        "---\n\n# Plan\n",
        encoding="utf-8",
    )
    adr.write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#state-mutation'\n"
        "date: '2026-05-15'\n"
        "related: []\n"
        "---\n\n# ADR\n",
        encoding="utf-8",
    )


class TestVaultRepair:
    def test_help_lists_repair_command(
        self,
        factory: WorkspaceFactory,
        runner: CliRunner,
    ) -> None:
        factory.install("core")

        result = runner.invoke(app, ["--target", str(factory.path), "vault", "--help"])

        assert result.exit_code == 0
        assert "repair" in result.output

    def test_dry_run_reports_index_plan_without_writing(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-dry-run",
            "repair-dry-run",
        )
        index_path = factory.path / ".vault" / "index" / "repair-dry-run.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-dry-run",
            "--dry-run",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0
        assert payload["dry_run"] is True
        assert payload["changed_files"] == []
        assert ".vault/index/repair-dry-run.index.md" in payload["generated_indexes"]
        assert not index_path.exists()

    def test_repair_refreshes_feature_index(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-index",
            "repair-index",
        )
        index_path = factory.path / ".vault" / "index" / "repair-index.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-index",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0
        assert index_path.exists()
        assert ".vault/index/repair-index.index.md" in payload["generated_indexes"]
        assert ".vault/index/repair-index.index.md" in payload["changed_files"]

    def test_repair_does_not_report_unchanged_index_as_modified(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-index-stable",
            "repair-index-stable",
        )

        first = run_repair_pipeline(factory.path, feature="repair-index-stable")
        second = run_repair_pipeline(factory.path, feature="repair-index-stable")

        index_rel = ".vault/index/repair-index-stable.index.md"
        assert index_rel in first.changed_files
        assert index_rel not in second.changed_files

    def test_repair_tracks_changed_indexes_in_configured_docs_dir(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        old_docs_dir = os.environ.get("VAULTSPEC_DOCS_DIR")
        os.environ["VAULTSPEC_DOCS_DIR"] = "notes"
        reset_config()
        try:
            factory.install("core")
            _write_doc(
                factory.path,
                "research",
                "2026-05-15-repair-custom-docs",
                "repair-custom-docs",
                docs_dir="notes",
            )
            index_path = (
                factory.path / "notes" / "index" / "repair-custom-docs.index.md"
            )

            run = run_repair_pipeline(factory.path, feature="repair-custom-docs")

            assert index_path.exists()
            assert "notes/index/repair-custom-docs.index.md" in run.generated_indexes
            assert "notes/index/repair-custom-docs.index.md" in run.changed_files
        finally:
            if old_docs_dir is None:
                os.environ.pop("VAULTSPEC_DOCS_DIR", None)
            else:
                os.environ["VAULTSPEC_DOCS_DIR"] = old_docs_dir
            reset_config()

    def test_repair_rebuilds_snapshot_after_structure_rename(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        upper = (
            factory.path
            / ".vault"
            / "research"
            / "2026-05-15-Repair-Stale-Snapshot-research.md"
        )
        lower = (
            factory.path
            / ".vault"
            / "research"
            / "2026-05-15-repair-stale-snapshot-research.md"
        )
        upper.parent.mkdir(parents=True, exist_ok=True)
        upper.write_text(
            "---\n"
            "tags:\n"
            "  - research\n"
            "  - repair-stale-snapshot\n"
            "date: '2026-05-15'\n"
            "related: []\n"
            "---\n\n# Stale Snapshot\n",
            encoding="utf-8",
        )

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-stale-snapshot",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0, result.output
        assert lower.exists()
        repaired = lower.read_text(encoding="utf-8")
        assert "#research" in repaired
        assert "#repair-stale-snapshot" in repaired
        assert payload["fixed_count"] >= 2

    def test_repair_strips_template_annotations(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        doc = _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-annotations",
            "repair-annotations",
        )
        annotated = doc.read_text(encoding="utf-8").replace(
            "---\n\n# 2026-05-15-repair-annotations\n",
            "---\n\n<!-- Fill this generated scaffold. -->\n\n"
            "# 2026-05-15-repair-annotations\n",
        )
        doc.write_text(annotated, encoding="utf-8")

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-annotations",
            "--no-index",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0, result.output
        assert payload["fixed_count"] >= 1
        assert "<!-- Fill this generated scaffold. -->" not in doc.read_text(
            encoding="utf-8"
        )

    def test_sanitize_annotations_command_strips_without_index_refresh(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        doc = _write_doc(
            factory.path,
            "research",
            "2026-05-15-sanitize-command",
            "sanitize-command",
        )
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + "\n<!-- Remove this generated annotation. -->\n",
            encoding="utf-8",
        )
        index_path = factory.path / ".vault" / "index" / "sanitize-command.index.md"

        result = factory.run(
            "vault",
            "sanitize",
            "annotations",
            "--feature",
            "sanitize-command",
            "--json",
        )
        payload = json.loads(result.output)

        assert result.exit_code == 0, result.output
        assert payload["fixed_count"] == 1
        assert not index_path.exists()
        assert "<!-- Remove this generated annotation. -->" not in doc.read_text(
            encoding="utf-8"
        )

    def test_sanitize_annotations_dry_run_does_not_strip(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        doc = _write_doc(
            factory.path,
            "research",
            "2026-05-15-sanitize-dry-run",
            "sanitize-dry-run",
        )
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + "\n<!-- Preview this generated annotation. -->\n",
            encoding="utf-8",
        )

        result = factory.run(
            "vault",
            "sanitize",
            "annotations",
            "--feature",
            "sanitize-dry-run",
            "--dry-run",
            "--json",
        )
        payload = json.loads(result.output)

        assert result.exit_code == 0
        assert payload["fixed_count"] == 0
        assert (
            sum(1 for diag in payload["diagnostics"] if diag["severity"] == "warning")
            == 1
        )
        assert (
            "Would remove template annotations" in payload["diagnostics"][0]["message"]
        )
        assert "<!-- Preview this generated annotation. -->" in doc.read_text(
            encoding="utf-8"
        )

    def test_check_all_fix_synchronizes_graph_after_cascaded_mutations(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "dummy-repo"
        root.mkdir()
        _write_state_mutation_workspace(root)

        results = run_all_checks(root, feature="state-mutation", fix=True)
        postcheck = run_all_checks(root, feature="state-mutation", fix=False)

        lower_research = (
            root / ".vault" / "research" / "2026-05-15-state-mutation-research.md"
        )
        upper_research = (
            root / ".vault" / "research" / "2026-05-15-State-Mutation-research.md"
        )
        plan = root / ".vault" / "plan" / "2026-05-15-state-mutation-plan.md"
        adr = root / ".vault" / "adr" / "2026-05-15-state-mutation-adr.md"

        assert sum(result.fixed_count for result in results) >= 6
        research_names = {path.name for path in lower_research.parent.iterdir()}
        assert lower_research.name in research_names
        assert upper_research.name not in research_names
        lower_text = lower_research.read_text(encoding="utf-8")
        assert "#research" in lower_text
        assert "#state-mutation" in lower_text

        plan_text = plan.read_text(encoding="utf-8")
        assert ".md]]" not in plan_text
        assert "[[missing-target]]" not in plan_text
        assert "[[2026-05-15-state-mutation-research]]" in plan_text
        assert "[[2026-05-15-state-mutation-adr]]" in plan_text
        assert "[[2026-05-15-state-mutation-research]]" in adr.read_text(
            encoding="utf-8"
        )
        assert all(result.error_count == 0 for result in postcheck)
        postcheck_warnings = [
            diag.message
            for result in postcheck
            for diag in result.diagnostics
            if diag.severity == "warning"
        ]
        assert postcheck_warnings == [
            "Feature 'state-mutation' has no feature index. Run "
            "vaultspec-core vault feature index to generate "
            "index/state-mutation.index.md"
        ]

    def test_repair_changed_files_tracks_cascaded_tmp_workspace_mutations(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "dummy-repo"
        root.mkdir()
        _write_state_mutation_workspace(root)

        run = run_repair_pipeline(
            root,
            feature="state-mutation",
            include_index=True,
        )

        assert run.error_count == 0
        assert run.warning_count == 0
        assert ".vault/plan/2026-05-15-state-mutation-plan.md" in run.changed_files
        assert ".vault/adr/2026-05-15-state-mutation-adr.md" in run.changed_files
        assert (
            ".vault/research/2026-05-15-State-Mutation-research.md" in run.changed_files
        )
        assert (
            ".vault/research/2026-05-15-state-mutation-research.md" in run.changed_files
        )
        assert ".vault/index/state-mutation.index.md" in run.changed_files

    def test_repair_fingerprints_skip_internal_vault_directories(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "dummy-repo"
        root.mkdir()
        _write_doc(root, "research", "2026-05-15-visible", "visible")
        for rel_path in (
            ".vault/.obsidian/state.md",
            ".vault/.trash/deleted.md",
            ".vault/data/cache.md",
            ".vault/logs/trace.md",
            ".vault/_archive/old.md",
        ):
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# internal\n", encoding="utf-8")

        fingerprints = _vault_file_fingerprints(root)

        assert ".vault/research/2026-05-15-visible-research.md" in fingerprints
        assert all("obsidian" not in path for path in fingerprints)
        assert all(".trash" not in path for path in fingerprints)
        assert all("/data/" not in path for path in fingerprints)
        assert all("/logs/" not in path for path in fingerprints)
        assert all("_archive" not in path for path in fingerprints)

    def test_repair_dry_run_journal_matches_planned_mutation_classes(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "dummy-repo"
        root.mkdir()
        _write_state_mutation_workspace(root)

        run = run_repair_pipeline(
            root,
            feature="state-mutation",
            dry_run=True,
            include_index=True,
        )

        assert run.changed_files == []
        assert not (root / ".vault" / "index" / "state-mutation.index.md").exists()
        planned_actions = {
            (entry["phase"], entry["action"], entry["status"]) for entry in run.journal
        }
        assert ("fix", "planned-fix", "planned") in planned_actions
        assert ("index", "refresh-index", "planned") in planned_actions

    def test_repair_reports_partial_failure_when_index_refresh_fails(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "dummy-repo"
        root.mkdir()
        _write_state_mutation_workspace(root)
        index_dir_collision = root / ".vault" / "index"
        index_dir_collision.write_text("not a directory", encoding="utf-8")

        run = run_repair_pipeline(
            root,
            feature="state-mutation",
            include_index=True,
        )

        assert run.partial_failure is True
        assert run.error_count >= 1
        assert any(
            entry["phase"] == "index" and entry["status"] == "failed"
            for entry in run.journal
        )
        assert any(item["check"] == "index" for item in run.unresolved)
        assert any(
            phase.get("phase") == "index" and phase.get("failed") is True
            for phase in run.phases
        )
        assert run.generated_indexes == []
        assert index_dir_collision.is_file()

    def test_dry_run_does_not_plan_index_for_unknown_feature(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "missing-feature",
            "--dry-run",
            "--json",
        )
        payload = _json_payload(result.output)
        index_phase = next(p for p in payload["phases"] if p["phase"] == "index")

        assert result.exit_code == 0
        assert payload["generated_indexes"] == []
        assert index_phase["planned"] == []

    def test_no_index_skips_generated_artifact_refresh(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-skip-index",
            "repair-skip-index",
        )
        index_path = factory.path / ".vault" / "index" / "repair-skip-index.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-skip-index",
            "--no-index",
            "--json",
        )
        payload = _json_payload(result.output)
        index_phase = next(p for p in payload["phases"] if p["phase"] == "index")

        assert result.exit_code == 0
        assert index_phase["skipped"] is True
        assert payload["generated_indexes"] == []
        assert not index_path.exists()

    def test_check_order_and_info_visibility_are_stable(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "adr",
            "2026-05-15-info-visibility",
            "info-visibility",
        )

        json_result = factory.run("vault", "check", "all", "--json")
        payload = json.loads(json_result.output)
        assert [item["check_name"] for item in payload] == [
            "structure",
            "frontmatter",
            "annotations",
            "links",
            "dangling",
            "body-links",
            "orphans",
            "features",
            "references",
            "schema",
        ]

        factory.run("vault", "feature", "index", "--feature", "info-visibility")
        default_result = factory.run(
            "vault",
            "check",
            "features",
            "--feature",
            "info-visibility",
        )
        verbose_result = factory.run(
            "vault",
            "check",
            "features",
            "--feature",
            "info-visibility",
            "--verbose",
        )

        assert "research document" not in default_result.output
        assert "research document" in verbose_result.output

    def test_repair_human_output_prioritizes_severity_before_truncating(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = RepairRun(dry_run=False)
        run.unresolved = [
            {
                "severity": "warning",
                "path": None,
                "message": f"warning {index}",
            }
            for index in range(25)
        ]
        run.unresolved.extend(
            {
                "severity": "info",
                "path": None,
                "message": f"informational {index}",
            }
            for index in range(3)
        )
        run.unresolved.append(
            {
                "severity": "error",
                "path": ".vault/plan/example.md",
                "message": "actionable failure",
            }
        )

        _render_repair_run(run)
        output = capsys.readouterr().out

        assert "actionable failure" in output
        assert output.index("actionable failure") < output.index("warning 0")
        assert "warning 20" not in output
        assert "informational 0" not in output
        assert "3 INFO diagnostics hidden" in output
        assert "6 more non-INFO diagnostics" in output

    def test_repair_human_output_counts_hidden_info_when_no_visible_items(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = RepairRun(dry_run=False)
        run.unresolved = [
            {
                "severity": "info",
                "path": None,
                "message": f"informational {index}",
            }
            for index in range(3)
        ]

        _render_repair_run(run)
        output = capsys.readouterr().out

        assert "informational 0" not in output
        assert "3 INFO diagnostics hidden" in output
