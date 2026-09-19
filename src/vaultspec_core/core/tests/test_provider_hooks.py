"""Tests for the provider-hooks subsystem (author once, render per provider).

Covers canonical-event rendering for every provider, the source loader, the
ownership-preserving compose step, and an end-to-end sync that writes each
provider's native hook-config file.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import ProviderCapability, Tool
from vaultspec_core.core.provider_hooks import (
    HookEvent,
    HookSpec,
    compose_flat_hooks,
    hook_targets,
    load_provider_hook_specs,
    render_hooks_payload,
    supported_events,
)
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _spec(
    event: HookEvent,
    *,
    name: str = "h",
    command: str = "echo x",
    matcher: str = "",
    timeout: int | None = None,
    enabled: bool = True,
) -> HookSpec:
    return HookSpec(
        name=name,
        event=event,
        command=command,
        matcher=matcher,
        timeout=timeout,
        enabled=enabled,
    )


@pytest.fixture
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the consent ledger away from the operator's real home.

    Redirects the one function whose job is locating that file, rather than
    patching ``Path.home``: the latter sends pathlib's own internals into
    unbounded recursion under a CLI runner, and this keeps the consent logic
    itself under test. The home is kept outside the workspace so the
    machine-global ``.vaultspec`` cannot collide with the workspace's own.
    """
    from vaultspec_core.triggers import trust

    ledger = tmp_path / "operator-home" / ".vaultspec" / trust.TRUST_FILE_NAME
    ledger.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(trust, "trust_file_path", lambda home=None: ledger)
    return ledger


class TestRenderPayload:
    def test_claude_uses_pretooluse_and_seconds(self):
        specs = [_spec(HookEvent.PRE_TOOL_USE, matcher="Bash", timeout=30)]
        payload = render_hooks_payload(specs, Tool.CLAUDE)
        assert payload is not None
        group = payload["PreToolUse"][0]
        assert group["matcher"] == "Bash"
        assert group["hooks"][0] == {
            "type": "command",
            "command": "echo x",
            "timeout": 30,
        }

    def test_gemini_maps_to_beforetool_and_milliseconds(self):
        specs = [_spec(HookEvent.PRE_TOOL_USE, timeout=30)]
        payload = render_hooks_payload(specs, Tool.GEMINI)
        assert payload is not None
        assert "BeforeTool" in payload
        assert "PreToolUse" not in payload
        assert payload["BeforeTool"][0]["hooks"][0]["timeout"] == 30000

    def test_post_tool_use_maps_to_aftertool_for_gemini(self):
        payload = render_hooks_payload([_spec(HookEvent.POST_TOOL_USE)], Tool.GEMINI)
        assert payload is not None and "AfterTool" in payload

    def test_antigravity_maps_only_events_the_binary_fires(self):
        """agy fires five events; three we once mapped are not among them.

        A hook rendered under a name agy never fires is written, reported as
        synced, and silently never runs - so the map is asserted exactly rather
        than by spot check.
        """
        assert supported_events(Tool.ANTIGRAVITY) == {
            HookEvent.PRE_TOOL_USE,
            HookEvent.POST_TOOL_USE,
            HookEvent.STOP,
        }

    def test_antigravity_non_tool_events_are_a_flat_handler_list(self):
        """agy's Stop takes handlers directly; a matcher group there is inert."""
        payload = render_hooks_payload([_spec(HookEvent.STOP)], Tool.ANTIGRAVITY)
        assert payload is not None
        stop = payload["vaultspec"]["Stop"]
        assert stop == [{"type": "command", "command": "echo x"}]

    def test_antigravity_tool_events_keep_the_matcher_group(self):
        payload = render_hooks_payload(
            [_spec(HookEvent.PRE_TOOL_USE, matcher="run_command")], Tool.ANTIGRAVITY
        )
        assert payload is not None
        group = payload["vaultspec"]["PreToolUse"][0]
        assert group["matcher"] == "run_command"
        assert group["hooks"] == [{"type": "command", "command": "echo x"}]

    def test_codex_supports_session_end(self):
        """Verified against Codex's published hook reference."""
        assert HookEvent.SESSION_END in supported_events(Tool.CODEX)
        assert HookEvent.NOTIFICATION not in supported_events(Tool.CODEX)

    def test_antigravity_wraps_in_named_hookset(self):
        payload = render_hooks_payload(
            [_spec(HookEvent.PRE_TOOL_USE)], Tool.ANTIGRAVITY
        )
        assert payload is not None
        assert set(payload) == {"vaultspec"}
        assert payload["vaultspec"]["enabled"] is True
        assert "PreToolUse" in payload["vaultspec"]

    def test_unsupported_event_skipped_with_warning(self):
        # Codex has no Notification event; Gemini has no Stop event.
        warnings: list[str] = []
        assert (
            render_hooks_payload([_spec(HookEvent.NOTIFICATION)], Tool.CODEX, warnings)
            is None
        )
        assert any("codex" in w for w in warnings)

        warnings.clear()
        assert (
            render_hooks_payload([_spec(HookEvent.STOP)], Tool.GEMINI, warnings) is None
        )
        assert any("gemini" in w for w in warnings)

    def test_empty_matcher_is_omitted(self):
        payload = render_hooks_payload([_spec(HookEvent.SESSION_START)], Tool.CLAUDE)
        assert payload is not None
        assert "matcher" not in payload["SessionStart"][0]

    def test_disabled_spec_not_rendered(self):
        assert (
            render_hooks_payload(
                [_spec(HookEvent.PRE_TOOL_USE, enabled=False)], Tool.CLAUDE
            )
            is None
        )

    def test_supported_events_matrix(self):
        assert HookEvent.STOP in supported_events(Tool.CLAUDE)
        assert HookEvent.STOP not in supported_events(Tool.GEMINI)
        assert HookEvent.NOTIFICATION not in supported_events(Tool.CODEX)
        assert HookEvent.USER_PROMPT_SUBMIT not in supported_events(Tool.ANTIGRAVITY)
        assert HookEvent.SESSION_START not in supported_events(Tool.ANTIGRAVITY)


class TestLoader:
    def test_loads_canonical_events_and_ignores_lifecycle(self, tmp_path: Path):
        (tmp_path / "guard.yaml").write_text(
            "event: pre_tool_use\nmatcher: Bash\ncommand: echo guard\ntimeout: 5\n",
            encoding="utf-8",
        )
        # A CLI-lifecycle hook (non-canonical event) must be ignored here.
        (tmp_path / "lifecycle.yaml").write_text(
            "event: config.synced\nactions:\n  - type: shell\n    command: echo doc\n",
            encoding="utf-8",
        )
        specs = load_provider_hook_specs(tmp_path)
        assert [s.name for s in specs] == ["guard"]
        assert specs[0].event is HookEvent.PRE_TOOL_USE
        assert specs[0].matcher == "Bash"
        assert specs[0].timeout == 5

    def test_command_from_actions_list(self, tmp_path: Path):
        (tmp_path / "a.yaml").write_text(
            "event: stop\nactions:\n  - type: shell\n    command: echo via-actions\n",
            encoding="utf-8",
        )
        specs = load_provider_hook_specs(tmp_path)
        assert specs[0].command == "echo via-actions"

    def test_missing_command_skipped(self, tmp_path: Path):
        (tmp_path / "bad.yaml").write_text("event: stop\n", encoding="utf-8")
        assert load_provider_hook_specs(tmp_path) == []


class TestComposeOwnership:
    def test_preserves_user_hooks_and_replaces_managed(self):
        user_group = {
            "matcher": "Write",
            "hooks": [{"type": "command", "command": "user"}],
        }
        existing = {"hooks": {"PreToolUse": [user_group]}, "otherSetting": True}

        payload1 = render_hooks_payload(
            [_spec(HookEvent.PRE_TOOL_USE, command="v1")], Tool.CLAUDE
        )
        native1, managed1 = compose_flat_hooks(existing, {}, payload1)
        # User group preserved, vaultspec group added, unrelated key intact.
        assert user_group in native1["hooks"]["PreToolUse"]
        assert native1["otherSetting"] is True
        # The native file must stay schema-pure: no in-file ownership key
        # (codex rejects unknown top-level fields and discards the whole file).
        assert "_vaultspecManagedHooks" not in native1
        assert any(
            g["hooks"][0]["command"] == "v1" for g in native1["hooks"]["PreToolUse"]
        )

        # Re-sync with a changed command: drop the old managed group (via the
        # sidecar record), keep the user's.
        payload2 = render_hooks_payload(
            [_spec(HookEvent.PRE_TOOL_USE, command="v2")], Tool.CLAUDE
        )
        native2, _managed2 = compose_flat_hooks(native1, managed1, payload2)
        cmds = [g["hooks"][0]["command"] for g in native2["hooks"]["PreToolUse"]]
        assert "user" in cmds and "v2" in cmds and "v1" not in cmds

    def test_removing_all_managed_clears_hooks_but_keeps_user(self):
        existing = {
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "user"}]}]}
        }
        payload = render_hooks_payload(
            [_spec(HookEvent.STOP, command="v1")], Tool.CLAUDE
        )
        with_managed, managed = compose_flat_hooks(existing, {}, payload)
        cleared, managed_after = compose_flat_hooks(with_managed, managed, None)
        cmds = [g["hooks"][0]["command"] for g in cleared["hooks"]["Stop"]]
        assert cmds == ["user"]
        assert managed_after == {}


class TestLaneSeparation:
    """Each loader owns a directory, so a foreign event is an error not a skip.

    While the two systems shared a directory, each loader silently skipped the
    other's events - which meant neither could tell a foreign event from a
    misspelled one of its own. Separate directories buy the right to complain.
    """

    def test_provider_loader_ignores_a_lifecycle_event_in_its_directory(
        self, tmp_path: Path
    ):
        (tmp_path / "doc.yaml").write_text(
            "event: config.synced\nactions:\n  - type: shell\n    command: echo doc\n",
            encoding="utf-8",
        )

        assert load_provider_hook_specs(tmp_path) == []

    def test_trigger_loader_warns_on_a_provider_event_in_its_directory(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        from vaultspec_core.triggers import load_triggers

        (tmp_path / "orient.yaml").write_text(
            "event: session_start\nactions:\n  - type: shell\n    command: echo hi\n",
            encoding="utf-8",
        )

        with caplog.at_level("WARNING"):
            loaded = load_triggers(tmp_path)

        assert loaded == []
        assert "unsupported event" in caplog.text
        assert "session_start" in caplog.text

    def test_trigger_loader_still_loads_its_own_event(self, tmp_path: Path):
        from vaultspec_core.triggers import load_triggers

        (tmp_path / "doc.yaml").write_text(
            "event: config.synced\nactions:\n  - type: shell\n    command: echo doc\n",
            encoding="utf-8",
        )

        assert {t.event for t in load_triggers(tmp_path)} == {"config.synced"}


class TestEndToEndSync:
    def test_sync_writes_native_files_per_provider(
        self, tmp_path: Path, isolated_ledger: Path
    ):
        factory = WorkspaceFactory(tmp_path).install("all")
        hooks_dir = tmp_path / ".vaultspec" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "guard.yaml").write_text(
            "event: pre_tool_use\nmatcher: run_command\ncommand: echo GUARD\n",
            encoding="utf-8",
        )
        factory.trust_hooks().sync("all")

        agy = json.loads(
            (tmp_path / ".agents" / "hooks.json").read_text(encoding="utf-8")
        )
        assert agy["vaultspec"]["PreToolUse"][0]["matcher"] == "run_command"

        codex = json.loads(
            (tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8")
        )
        assert "PreToolUse" in codex["hooks"]
        # Regression: codex rejects unknown top-level keys and discards the
        # whole hooks file. The native file must carry only ``hooks``;
        # ownership lives in a sidecar beside it.
        assert "_vaultspecManagedHooks" not in codex
        assert set(codex) == {"hooks"}
        assert (tmp_path / ".codex" / ".vaultspec-hooks.json").exists()

        claude = json.loads(
            (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        assert "PreToolUse" in claude["hooks"]

        gemini = json.loads(
            (tmp_path / ".gemini" / "settings.json").read_text(encoding="utf-8")
        )
        assert "BeforeTool" in gemini["hooks"]


class TestHookTargets:
    """The set a status surface reports must be the set the renderer writes."""

    def test_targets_match_the_files_sync_actually_writes(
        self, tmp_path: Path, isolated_ledger: Path
    ):
        factory = WorkspaceFactory(tmp_path).install("all")
        hooks_dir = tmp_path / ".vaultspec" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "guard.yaml").write_text(
            "event: pre_tool_use\ncommand: echo GUARD\n", encoding="utf-8"
        )

        factory.trust_hooks().sync("all")
        targets = hook_targets()

        assert targets, "an all-provider install has hook-capable providers"
        for _tool, native, _sidecar in targets:
            assert native.exists(), f"{native} was reported but never written"

    def test_only_antigravity_has_no_sidecar(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all").sync("all")

        by_tool = {tool: sidecar for tool, _native, sidecar in hook_targets()}

        assert by_tool[Tool.ANTIGRAVITY] is None, "agy owns a named hookset"
        assert all(
            sidecar is not None
            for tool, sidecar in by_tool.items()
            if tool is not Tool.ANTIGRAVITY
        )

    def test_every_target_declares_the_hooks_capability(self, tmp_path: Path):
        from vaultspec_core.core.manifest import installed_tool_configs

        WorkspaceFactory(tmp_path).install("all").sync("all")
        configs = installed_tool_configs()

        for tool, _native, _sidecar in hook_targets():
            assert ProviderCapability.HOOKS in configs[tool].capabilities
