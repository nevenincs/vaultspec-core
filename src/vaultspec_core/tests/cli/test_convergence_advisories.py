"""Doctor advisories for convergence holes core cannot fix itself.

Exercises the two warn-only diagnosis surfaces added alongside automatic
launch convergence: the ``UNREFRESHABLE`` precommit signal for prek.toml
workspaces whose stale YAML hooks the scaffold will never touch, and the
stale package-seed collector for builtin MCP definitions still in a static
pre-mode shape. Both render as warnings but never fail the doctor, because
their remediation lives outside the workspace.
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

    def test_unrefreshable_never_fails_the_doctor(self, tmp_path: Path) -> None:
        """The advisory is warn-only: the exit-code policy ignores it."""
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal

        diag = WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            precommit=PrecommitSignal.UNREFRESHABLE,
        )
        assert _doctor_exit_code(diag) == 0


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
