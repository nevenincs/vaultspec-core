"""Tests for the agent-runtime hook rows in ``vaultspec-core spec doctor``.

Before these rows existed, a workspace whose hooks had reached no provider was
indistinguishable from one whose hooks had reached all of them: nothing in the
report mentioned them either way. Each test drives the real CLI against a real
install so what the doctor reads is what a sync actually wrote.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _write_hook(root: Path, event: str = "pre_tool_use", name: str = "guard") -> Path:
    hooks_dir = root / ".vaultspec" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    path = hooks_dir / f"{name}.yaml"
    path.write_text(
        f"event: {event}\nmatcher: Bash\ncommand: echo GUARD\n", encoding="utf-8"
    )
    return path


def _hook_report(factory: WorkspaceFactory) -> list[dict[str, object]]:
    result = factory.run("spec", "doctor", "--json")
    data = json.loads(result.output)["data"]
    reports = data["home"]["provider_hooks"]
    assert isinstance(reports, list)
    return reports


class TestNoHooksDeclared:
    def test_a_workspace_with_no_hooks_stays_healthy(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        result = factory.run("spec", "doctor")

        assert result.exit_code == 0, result.output
        assert "no hooks declared" in result.output

    def test_every_hook_capable_provider_is_reported(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        tools = {str(report["tool"]) for report in _hook_report(factory)}

        assert tools == {"claude", "codex", "gemini", "antigravity"}


class TestUnrenderedHooksAreVisible:
    def test_a_declared_hook_that_never_synced_warns(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)

        result = factory.run("spec", "doctor")
        assert result.exit_code == 1, result.output
        assert "never rendered" in result.output

    def test_the_row_names_the_providers_it_applies_to(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)

        output = factory.run("spec", "doctor").output
        for tool in ("claude", "codex", "gemini", "antigravity"):
            assert tool in output

    def test_a_synced_hook_reports_healthy(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output
        assert "rendered and recorded" in result.output

    def test_a_deleted_sidecar_warns_about_ownership(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        factory.sync("all")
        (tmp_path / ".claude" / ".vaultspec-hooks.json").unlink()

        result = factory.run("spec", "doctor")
        assert result.exit_code == 1, result.output
        assert "ownership record absent" in result.output
        assert "claude" in result.output

    def test_gate_errors_does_not_fail_on_a_hook_warning(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)

        # An unrendered hook is warning-weighted, so the pre-commit gate must
        # not block a commit over it.
        result = factory.run("spec", "doctor", "--gate-errors")
        assert result.exit_code == 0, result.output


class TestUnsupportedEventAdvisory:
    def test_an_event_a_provider_lacks_is_reported_without_failing(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path, event="user_prompt_submit", name="ask")
        factory.sync("all")

        result = factory.run("spec", "doctor")
        # gemini and antigravity have no UserPromptSubmit equivalent, so the
        # hook is silently skipped for them. That is expected, not a fault.
        assert result.exit_code == 0, result.output
        assert "ask (user_prompt_submit)" in result.output
        assert "not supported by" in result.output

    def test_no_advisory_when_every_provider_supports_the_event(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path, event="session_start", name="orient")
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output
        assert "not supported by" not in result.output


class TestJsonSurface:
    def test_each_report_carries_its_signal_and_path(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        factory.sync("all")

        by_tool = {str(r["tool"]): r for r in _hook_report(factory)}
        claude = by_tool["claude"]

        assert claude["signal"] == "in_sync"
        assert str(claude["native_path"]).endswith("settings.json")
        assert claude["unsupported"] == []

    def test_an_unrendered_hook_is_machine_readable(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)

        signals = {str(r["signal"]) for r in _hook_report(factory)}
        assert signals == {"not_rendered"}
