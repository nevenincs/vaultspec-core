"""Doctor advisories for convergence holes core cannot fix itself.

Exercises the diagnosis surfaces around the prek boundary and the stale
package-seed collector. The precommit signal is content-aware: it reads
``prek.toml`` through the boundary predicate, so ``UNREFRESHABLE`` fires
only when the canonical hooks are genuinely absent from ``prek.toml``
(a real problem, warn-level, remediable with ``spec precommit migrate``),
while a superseded ``.pre-commit-config.yaml`` next to a healthy
``prek.toml`` reports the benign ``ORPHANED`` state that never fails the
doctor.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors import (
    collect_precommit_state,
    collect_stale_seed_definitions,
)
from vaultspec_core.core.diagnosis.signals import PrecommitSignal
from vaultspec_core.core.mcps import _MODE_COMMAND_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _write_prek_hooks(root: Path) -> None:
    """Write a prek.toml carrying the full canonical hook set."""
    from vaultspec_core.core.enums import InstallMode
    from vaultspec_core.core.prek_boundary import render_prek_hook_block

    (root / "prek.toml").write_text(
        render_prek_hook_block(InstallMode.DEPENDENCY), encoding="utf-8"
    )


def _write_yaml_hooks(root: Path, entry: str) -> None:
    """Write a .pre-commit-config.yaml carrying one stale canonical hook."""
    from vaultspec_core.core.commands import CANONICAL_HOOK_IDS

    hook_id = sorted(CANONICAL_HOOK_IDS)[0]
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "- repo: local\n"
        "  hooks:\n"
        f"  - id: {hook_id}\n"
        f"    entry: {entry}\n"
        "    language: system\n",
        encoding="utf-8",
    )


class TestPrekUnrefreshableAdvisory:
    def test_stale_hooks_with_prek_toml_report_unrefreshable(
        self, tmp_path: Path
    ) -> None:
        """prek.toml plus a non-canonical YAML hook set is UNREFRESHABLE,
        not the generic staleness whose fix hint the scaffold cannot honor."""
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")
        (tmp_path / "prek.toml").write_text("", encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.UNREFRESHABLE

    def test_stale_hooks_without_prek_toml_keep_existing_signal(
        self, tmp_path: Path
    ) -> None:
        """Without prek.toml the YAML state reports as before (refreshable)."""
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.INCOMPLETE

    def test_unrefreshable_warns_the_doctor(self, tmp_path: Path) -> None:
        """Content-verified genuine stranding is a warning: prek.toml owns
        the boundary, lacks the canonical hooks, and nothing runs them."""
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal

        diag = WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            precommit=PrecommitSignal.UNREFRESHABLE,
        )
        assert _doctor_exit_code(diag) == 1

    def test_orphaned_never_fails_the_doctor(self, tmp_path: Path) -> None:
        """A superseded YAML next to a healthy prek.toml is benign info."""
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal

        diag = WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            precommit=PrecommitSignal.ORPHANED,
        )
        assert _doctor_exit_code(diag) == 0


class TestPrekContentAwareSignal:
    """The precommit signal reflects prek.toml contents, not existence."""

    def test_healthy_prek_with_stale_yaml_reports_orphaned(
        self, tmp_path: Path
    ) -> None:
        _write_prek_hooks(tmp_path)
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.ORPHANED

    def test_healthy_prek_with_complete_yaml_reports_orphaned(
        self, tmp_path: Path
    ) -> None:
        """Even a fully canonical YAML is superseded: prek never reads it."""
        from vaultspec_core.core.commands import _scaffold_precommit

        _scaffold_precommit(tmp_path)
        assert collect_precommit_state(tmp_path) is PrecommitSignal.COMPLETE

        _write_prek_hooks(tmp_path)
        assert collect_precommit_state(tmp_path) is PrecommitSignal.ORPHANED

    def test_healthy_prek_without_yaml_reports_complete(self, tmp_path: Path) -> None:
        _write_prek_hooks(tmp_path)

        assert collect_precommit_state(tmp_path) is PrecommitSignal.COMPLETE

    def test_empty_prek_without_yaml_reports_unrefreshable(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "prek.toml").write_text("", encoding="utf-8")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.UNREFRESHABLE

    def test_partial_prek_hooks_report_unrefreshable(self, tmp_path: Path) -> None:
        from vaultspec_core.core.commands import CANONICAL_HOOK_IDS

        hook_id = sorted(CANONICAL_HOOK_IDS)[0]
        (tmp_path / "prek.toml").write_text(
            "[[repos]]\n"
            'repo = "local"\n\n'
            "[[repos.hooks]]\n"
            f'id = "{hook_id}"\n'
            'entry = "echo partial"\n'
            'language = "system"\n',
            encoding="utf-8",
        )

        assert collect_precommit_state(tmp_path) is PrecommitSignal.UNREFRESHABLE

    def test_unparseable_prek_reports_unrefreshable(self, tmp_path: Path) -> None:
        """A broken prek.toml is conservatively hooks-absent, never healthy."""
        (tmp_path / "prek.toml").write_text("[[repos\nnot toml", encoding="utf-8")
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        assert collect_precommit_state(tmp_path) is PrecommitSignal.UNREFRESHABLE


class TestDoctorPrekAdvisoryText:
    """The doctor row names the actual remediation for each prek state."""

    def test_unrefreshable_advisory_names_migrate_verb(self, runner, factory) -> None:
        from vaultspec_core.tests.cli.conftest import run_spec

        factory.install()
        (factory.path / "prek.toml").write_text("", encoding="utf-8")

        result = run_spec(runner, "spec", "doctor", target=factory.path)

        assert "spec precommit migrate" in result.output

    def test_orphaned_advisory_names_superseded_yaml(self, runner, factory) -> None:
        from vaultspec_core.tests.cli.conftest import run_spec

        factory.install()
        _write_prek_hooks(factory.path)

        result = run_spec(runner, "spec", "doctor", target=factory.path)

        assert "superseded .pre-commit-config.yaml" in result.output


class TestGatedOrphanCleanup:
    """YAML removal is operator-gated and verified, never automatic."""

    def test_remove_refused_on_conflicting_prek(self, tmp_path: Path) -> None:
        """Canonical IDs outside the managed block refuse the whole run,
        including removal: the YAML must survive."""
        from vaultspec_core.core.commands import CANONICAL_HOOK_IDS
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        hook_id = sorted(CANONICAL_HOOK_IDS)[0]
        (tmp_path / "prek.toml").write_text(
            "[[repos]]\n"
            'repo = "local"\n\n'
            "[[repos.hooks]]\n"
            f'id = "{hook_id}"\n'
            'entry = "echo operator-authored"\n'
            'language = "system"\n',
            encoding="utf-8",
        )
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        result = migrate_hooks_to_prek(tmp_path, remove_yaml=True)

        assert result.status == "conflicting"
        assert result.yaml_removed is False
        assert (tmp_path / ".pre-commit-config.yaml").exists()

    def test_remove_after_migration_clears_orphan(self, tmp_path: Path) -> None:
        """migrate --remove-yaml transplants, verifies, deletes, and the
        ORPHANED signal clears to COMPLETE."""
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        (tmp_path / "prek.toml").write_text("", encoding="utf-8")
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        result = migrate_hooks_to_prek(tmp_path, remove_yaml=True)

        assert result.status == "migrated"
        assert result.yaml_removed is True
        assert not (tmp_path / ".pre-commit-config.yaml").exists()
        assert collect_precommit_state(tmp_path) is PrecommitSignal.COMPLETE

    def test_remove_with_hooks_already_present(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        _write_prek_hooks(tmp_path)
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")
        assert collect_precommit_state(tmp_path) is PrecommitSignal.ORPHANED

        result = migrate_hooks_to_prek(tmp_path, remove_yaml=True)

        assert result.status == "unchanged"
        assert result.yaml_removed is True
        assert not (tmp_path / ".pre-commit-config.yaml").exists()
        assert collect_precommit_state(tmp_path) is PrecommitSignal.COMPLETE

    def test_migrate_without_flag_keeps_yaml(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import migrate_hooks_to_prek

        (tmp_path / "prek.toml").write_text("", encoding="utf-8")
        _write_yaml_hooks(tmp_path, "uv run vaultspec-core legacy-entry")

        result = migrate_hooks_to_prek(tmp_path)

        assert result.status == "migrated"
        assert result.yaml_removed is False
        assert (tmp_path / ".pre-commit-config.yaml").exists()


class TestStaleSeedAdvisory:
    def test_static_builtin_seed_is_reported(self, tmp_path: Path) -> None:
        """A package-bundled seed whose command is a concrete string (the
        pre-mode static shape) is named; tokenized seeds and custom
        definitions are not."""
        mcps = tmp_path / ".vaultspec" / "mcps"
        mcps.mkdir(parents=True)
        (mcps / "vaultspec-rag.builtin.json").write_text(
            json.dumps({"command": "uv", "args": ["run", "vaultspec-search-mcp"]}),
            encoding="utf-8",
        )
        (mcps / "vaultspec-core.builtin.json").write_text(
            json.dumps({"command": _MODE_COMMAND_TOKEN, "args": []}),
            encoding="utf-8",
        )
        (mcps / "my-server.json").write_text(
            json.dumps({"command": "node", "args": ["server.js"]}),
            encoding="utf-8",
        )

        assert collect_stale_seed_definitions(tmp_path) == ["vaultspec-rag"]

    def test_all_tokenized_seeds_report_clean(self, tmp_path: Path) -> None:
        mcps = tmp_path / ".vaultspec" / "mcps"
        mcps.mkdir(parents=True)
        (mcps / "vaultspec-core.builtin.json").write_text(
            json.dumps({"command": _MODE_COMMAND_TOKEN, "args": []}),
            encoding="utf-8",
        )

        assert collect_stale_seed_definitions(tmp_path) == []

    def test_missing_mcps_dir_reports_clean(self, tmp_path: Path) -> None:
        assert collect_stale_seed_definitions(tmp_path) == []

    def test_stale_seed_never_fails_the_doctor(self, tmp_path: Path) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal

        diag = WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            stale_mcp_seeds=["vaultspec-rag"],
        )
        assert _doctor_exit_code(diag) == 0
