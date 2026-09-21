"""Tests for the agent-runtime hook rows in ``vaultspec-core spec doctor``.

Before these rows existed, a workspace whose hooks had reached no provider was
indistinguishable from one whose hooks had reached all of them: nothing in the
report mentioned them either way. Each test drives the real CLI against a real
install so what the doctor reads is what a sync actually wrote.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

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


def _installed(tmp_path: Path) -> WorkspaceFactory:
    """Install with the consent ledger redirected away from the real one.

    The renderer refuses an unapproved hook, so a test that let it read the
    developer's own ledger would pass or fail on whatever they had approved.
    The redirect is at ``trust_file_path``, the one function whose job is
    locating that file, rather than at ``Path.home``, which the CLI runner also
    depends on.
    """
    return WorkspaceFactory(tmp_path).install("all")


def _hook_report(factory: WorkspaceFactory) -> list[dict[str, object]]:
    result = factory.run("spec", "doctor", "--json")
    envelope = cast("dict[str, Any]", json.loads(result.output))
    data = cast("dict[str, Any]", envelope["data"])
    home = cast("dict[str, Any]", data["home"])
    reports = home["provider_hooks"]
    assert isinstance(reports, list)
    return cast("list[dict[str, object]]", reports)


class TestNoHooksDeclared:
    def test_a_workspace_with_no_hooks_stays_healthy(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        result = factory.run("spec", "doctor")

        assert result.exit_code == 0, result.output
        assert "no hooks declared" in result.output

    def test_every_hook_capable_provider_is_reported(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        tools = {str(report["tool"]) for report in _hook_report(factory)}

        assert tools == {"claude", "codex", "gemini", "antigravity"}


class TestUnrenderedHooksAreVisible:
    def test_a_declared_hook_that_never_synced_warns(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        # Approved, so consent is not what is missing - only the sync is.
        factory.trust_hooks()

        result = factory.run("spec", "doctor")
        assert result.exit_code == 1, result.output
        assert "never rendered" in result.output

    def test_the_row_names_the_providers_it_applies_to(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)

        output = factory.run("spec", "doctor").output
        for tool in ("claude", "codex", "gemini", "antigravity"):
            assert tool in output

    def test_a_synced_hook_reports_healthy(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output
        assert "rendered and recorded" in result.output

    def test_a_deleted_sidecar_warns_about_ownership(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        (tmp_path / ".claude" / ".vaultspec-hooks.json").unlink()

        result = factory.run("spec", "doctor")
        assert result.exit_code == 1, result.output
        assert "ownership record absent" in result.output
        assert "claude" in result.output

    def test_gate_errors_does_not_fail_on_a_hook_warning(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)

        # An unrendered hook is warning-weighted, so the pre-commit gate must
        # not block a commit over it.
        result = factory.run("spec", "doctor", "--gate-errors")
        assert result.exit_code == 0, result.output


class TestAwaitingApproval:
    """An unapproved hook is a decision the operator has yet to make."""

    def test_it_does_not_read_as_a_missing_sync(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert "awaiting approval" in result.output
        # "run sync" would be the wrong advice: the sync already ran and
        # refused, and running it again changes nothing.
        assert "never rendered" not in result.output

    def test_it_does_not_raise_the_exit_code(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.sync("all")

        # The consent gate working as designed is not a fault to weigh, so a
        # workspace full of unapproved hooks still exits clean.
        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output

    def test_it_names_the_verb_that_approves(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.sync("all")

        assert "spec hooks trust" in factory.run("spec", "doctor").output

    def test_approving_and_syncing_clears_the_row(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.sync("all")
        factory.trust_hooks()
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert "awaiting approval" not in result.output
        assert "rendered and recorded" in result.output

    def test_the_json_surface_names_the_state(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.sync("all")

        signals = {str(r["signal"]) for r in _hook_report(factory)}
        assert signals == {"untrusted"}


class TestUnsupportedEventAdvisory:
    def test_an_event_a_provider_lacks_is_reported_without_failing(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path, event="user_prompt_submit", name="ask")
        factory.trust_hooks()
        factory.sync("all")

        result = factory.run("spec", "doctor")
        # gemini and antigravity have no UserPromptSubmit equivalent, so the
        # hook is silently skipped for them. That is expected, not a fault.
        assert result.exit_code == 0, result.output
        assert "ask (user_prompt_submit)" in result.output
        assert "not supported by" in result.output

    def test_no_advisory_when_every_provider_supports_the_event(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        # pre_tool_use is one of only two events every provider runs, so it
        # is the shape that must produce no advisory.
        _write_hook(tmp_path, event="pre_tool_use", name="guard-all")
        factory.trust_hooks()
        factory.sync("all")

        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, result.output
        assert "not supported by" not in result.output


class TestJsonSurface:
    def test_each_report_carries_its_signal_and_path(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        by_tool = {str(r["tool"]): r for r in _hook_report(factory)}
        claude = by_tool["claude"]

        assert claude["signal"] == "in_sync"
        assert str(claude["native_path"]).endswith("settings.json")
        assert claude["unsupported"] == []

    def test_an_unrendered_hook_is_machine_readable(
        self, tmp_path: Path, operator_home: Path
    ) -> None:
        factory = _installed(tmp_path)
        _write_hook(tmp_path)
        factory.trust_hooks()

        signals = {str(r["signal"]) for r in _hook_report(factory)}
        assert signals == {"not_rendered"}
