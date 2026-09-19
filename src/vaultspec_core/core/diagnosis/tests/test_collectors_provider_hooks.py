"""Tests for the provider-hook render collector.

Every case is built from a real ``WorkspaceFactory`` install and a real sync, so
the state the collector reads is the state the renderer actually produces rather
than a hand-written approximation of it. Drift cases are made by editing that
rendered output the way a user or a half-run sync would.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultspec_core.core.diagnosis.collectors_provider_hooks import (
    HookTarget,
    ProviderHookReport,
    collect_provider_hook_reports,
    worst_hook_signal,
)
from vaultspec_core.core.diagnosis.signals import ProviderHookSignal
from vaultspec_core.core.enums import Tool
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.unit]

#: The hookset name antigravity groups vaultspec-managed hooks under, as it
#: appears in ``.agents/hooks.json``.
_HOOKSET = "vaultspec"

_SIDECAR = ".vaultspec-hooks.json"


def _hooks_dir(root: Path) -> Path:
    path = root / ".vaultspec" / "hooks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_source(root: Path, name: str = "guard", event: str = "pre_tool_use") -> Path:
    path = _hooks_dir(root) / f"{name}.yaml"
    path.write_text(
        f"event: {event}\nmatcher: Bash\ncommand: echo GUARD\n", encoding="utf-8"
    )
    return path


def _claude_target(root: Path) -> HookTarget:
    return HookTarget(
        tool=Tool.CLAUDE,
        native=root / ".claude" / "settings.json",
        sidecar=root / ".claude" / _SIDECAR,
    )


def _agy_target(root: Path) -> HookTarget:
    return HookTarget(
        tool=Tool.ANTIGRAVITY,
        native=root / ".agents" / "hooks.json",
        hookset=_HOOKSET,
    )


def _installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkspaceFactory:
    """Install with the consent ledger redirected away from the real one.

    ``provider_hooks_sync`` refuses a hook the ledger does not carry, so a test
    that let it read the operator's own ledger would pass or fail on whatever
    that developer had approved. The redirect is at ``trust_file_path``, the one
    function whose job is locating that file, rather than at ``Path.home``,
    which pathlib and the CLI runner both depend on. The stand-in home sits
    outside the workspace, because the VaultSpec home is ``~/.vaultspec`` and
    aiming it at the workspace root would collide with the workspace's own.
    """
    from vaultspec_core.triggers import trust

    ledger = tmp_path / "operator-home" / ".vaultspec" / trust.TRUST_FILE_NAME
    ledger.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(trust, "trust_file_path", lambda home=None: ledger)
    return WorkspaceFactory(tmp_path).install("all")


def _only(reports: list[ProviderHookReport]) -> ProviderHookReport:
    assert len(reports) == 1
    return reports[0]


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class TestSidecarProvider:
    def test_no_sources_and_nothing_rendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _installed(tmp_path, monkeypatch)
        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.NO_SOURCES

    def test_a_completed_sync_reads_in_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.IN_SYNC

    def test_a_source_that_never_synced_reads_not_rendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        # Approved, so consent is not what is missing - only the sync is.
        factory.trust_hooks()

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.NOT_RENDERED

    def test_skipping_the_pass_is_visible_as_not_rendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all", skip={"hooks"})

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.NOT_RENDERED

    def test_a_deleted_sidecar_reads_sidecar_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        (tmp_path / ".claude" / _SIDECAR).unlink()

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.SIDECAR_MISSING

    def test_an_edited_source_reads_stale_not_unrendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        # Change the command without re-syncing. None of what the source now
        # renders is in the file, but the previous render is still live and the
        # ownership record proves it. That is drift, not an absent render -
        # reporting "never rendered" would point the operator at the wrong
        # thing.
        (_hooks_dir(tmp_path) / "guard.yaml").write_text(
            "event: pre_tool_use\nmatcher: Bash\ncommand: echo CHANGED\n",
            encoding="utf-8",
        )
        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.STALE

    def test_not_rendered_requires_nothing_managed_anywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        # Remove both the render and the record, leaving a declared source and
        # no trace of a sync. This is the only shape NOT_RENDERED describes.
        settings = _read(tmp_path / ".claude" / "settings.json")
        settings.pop("hooks", None)
        _write(tmp_path / ".claude" / "settings.json", settings)
        (tmp_path / ".claude" / ".vaultspec-hooks.json").unlink()

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.NOT_RENDERED

    def test_a_record_for_a_withdrawn_source_reads_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        source = _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        source.unlink()

        # The source is gone, so nothing should render, but the ownership
        # record still names entries a sync would have to prune.
        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.STALE

    def test_one_of_two_rendered_groups_reads_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path, name="guard")
        _write_source(tmp_path, name="watch", event="post_tool_use")
        factory.trust_hooks()
        factory.sync("all")

        # Remove one event's groups from the config, as a hand edit would.
        settings = _read(tmp_path / ".claude" / "settings.json")
        hooks = settings["hooks"]
        assert isinstance(hooks, dict)
        del hooks["PostToolUse"]
        _write(tmp_path / ".claude" / "settings.json", settings)

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.STALE

    def test_a_sidecar_that_disagrees_reads_sidecar_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        # The render is intact; the record claims an extra event, so a re-sync
        # would try to prune a group that is not vaultspec's.
        record = _read(tmp_path / ".claude" / _SIDECAR)
        record["SessionStart"] = [{"hooks": [{"type": "command", "command": "x"}]}]
        _write(tmp_path / ".claude" / _SIDECAR, record)

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.SIDECAR_STALE

    def test_hand_authored_hooks_do_not_make_it_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        settings = _read(tmp_path / ".claude" / "settings.json")
        hooks = settings["hooks"]
        assert isinstance(hooks, dict)
        hooks["SessionEnd"] = [{"hooks": [{"type": "command", "command": "mine"}]}]
        _write(tmp_path / ".claude" / "settings.json", settings)

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.IN_SYNC

    def test_unparseable_config_reads_unreadable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        (tmp_path / ".claude" / "settings.json").write_text("{ not json", "utf-8")

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.UNREADABLE

    def test_unparseable_sidecar_reads_unreadable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        (tmp_path / ".claude" / _SIDECAR).write_text("[]", encoding="utf-8")

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_claude_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.UNREADABLE


class TestHooksetProvider:
    def test_a_completed_sync_reads_in_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_agy_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.IN_SYNC

    def test_a_source_that_never_synced_reads_not_rendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        # Approved, so consent is not what is missing - only the sync is.
        factory.trust_hooks()

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_agy_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.NOT_RENDERED

    def test_a_withdrawn_source_leaves_the_hookset_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        source = _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")
        source.unlink()

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_agy_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.STALE

    def test_an_edited_hookset_reads_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        native = _read(tmp_path / ".agents" / "hooks.json")
        hookset = native[_HOOKSET]
        assert isinstance(hookset, dict)
        hookset["enabled"] = False
        _write(tmp_path / ".agents" / "hooks.json", native)

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_agy_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.STALE

    def test_a_foreign_hookset_is_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        native = _read(tmp_path / ".agents" / "hooks.json")
        native["someone-else"] = {"enabled": True}
        _write(tmp_path / ".agents" / "hooks.json", native)

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path), [_agy_target(tmp_path)]
        )
        assert _only(reports).signal is ProviderHookSignal.IN_SYNC


class TestUnsupportedEvents:
    def test_an_event_a_provider_lacks_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path, name="ask", event="user_prompt_submit")
        factory.trust_hooks()
        factory.sync("all")

        reports = collect_provider_hook_reports(
            _hooks_dir(tmp_path),
            [_claude_target(tmp_path), _agy_target(tmp_path)],
        )
        by_tool = {report.tool: report for report in reports}

        # Claude consumes UserPromptSubmit; antigravity has no equivalent.
        assert by_tool["claude"].unsupported == ()
        assert by_tool["antigravity"].unsupported == ("ask (user_prompt_submit)",)

    def test_a_provider_with_nothing_to_render_still_reads_benignly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path, name="ask", event="user_prompt_submit")
        factory.trust_hooks()
        factory.sync("all")

        # antigravity cannot consume the only hook declared, so there is
        # nothing for it to be out of sync about.
        report = _only(
            collect_provider_hook_reports(_hooks_dir(tmp_path), [_agy_target(tmp_path)])
        )
        assert report.signal is ProviderHookSignal.IN_SYNC

    def test_a_disabled_source_is_not_reported_as_unsupported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _installed(tmp_path, monkeypatch)
        (_hooks_dir(tmp_path) / "off.yaml").write_text(
            "event: user_prompt_submit\ncommand: echo x\nenabled: false\n",
            encoding="utf-8",
        )
        report = _only(
            collect_provider_hook_reports(_hooks_dir(tmp_path), [_agy_target(tmp_path)])
        )
        assert report.unsupported == ()


class TestConsent:
    """A hook nobody approved is a decision, not an un-run sync."""

    def test_an_unapproved_hook_reads_untrusted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        # Sync without approving: the renderer refuses, by design.
        factory.sync("all")

        report = _only(
            collect_provider_hook_reports(
                _hooks_dir(tmp_path), [_claude_target(tmp_path)]
            )
        )
        assert report.signal is ProviderHookSignal.UNTRUSTED

    def test_untrusted_is_not_reported_as_unrendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.sync("all")

        # The remedy for an unapproved hook is approval, not another sync, so
        # the verdict must not be the one whose advice is "run sync".
        report = _only(
            collect_provider_hook_reports(
                _hooks_dir(tmp_path), [_claude_target(tmp_path)]
            )
        )
        assert report.signal is not ProviderHookSignal.NOT_RENDERED

    def test_approving_then_syncing_clears_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.sync("all")
        factory.trust_hooks()
        factory.sync("all")

        report = _only(
            collect_provider_hook_reports(
                _hooks_dir(tmp_path), [_claude_target(tmp_path)]
            )
        )
        assert report.signal is ProviderHookSignal.IN_SYNC

    def test_editing_an_approved_hook_withdraws_consent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        factory = _installed(tmp_path, monkeypatch)
        _write_source(tmp_path)
        factory.trust_hooks()
        factory.sync("all")

        # Consent is per digest, so rewriting the file revokes it. The command
        # approved yesterday is still live in the agent's config, which is the
        # urgent half: it reads stale, and a sync does fix it by pruning what it
        # may no longer render.
        (_hooks_dir(tmp_path) / "guard.yaml").write_text(
            "event: pre_tool_use\nmatcher: Bash\ncommand: echo CHANGED\n",
            encoding="utf-8",
        )
        report = _only(
            collect_provider_hook_reports(
                _hooks_dir(tmp_path), [_claude_target(tmp_path)]
            )
        )
        assert report.signal is ProviderHookSignal.STALE

        # That sync withdraws the superseded command rather than leaving it
        # running, and what remains is a hook awaiting approval.
        factory.sync("all")
        settings_path = tmp_path / ".claude" / "settings.json"
        # A config left holding nothing is removed rather than emptied, so
        # either shape proves the command is gone.
        settings = _read(settings_path) if settings_path.exists() else {}
        hooks = settings.get("hooks", {})
        assert isinstance(hooks, dict)
        assert "PreToolUse" not in hooks

        report = _only(
            collect_provider_hook_reports(
                _hooks_dir(tmp_path), [_claude_target(tmp_path)]
            )
        )
        assert report.signal is ProviderHookSignal.UNTRUSTED

    def test_an_unsupported_event_is_still_reported_when_unapproved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _installed(tmp_path, monkeypatch)
        _write_source(tmp_path, name="ask", event="user_prompt_submit")

        # Worth knowing before the operator decides whether to approve it, so
        # the advisory is computed over every declared hook rather than only
        # the approved ones.
        report = _only(
            collect_provider_hook_reports(_hooks_dir(tmp_path), [_agy_target(tmp_path)])
        )
        assert report.unsupported == ("ask (user_prompt_submit)",)


class TestWorstSignal:
    def test_the_worst_of_several_providers_wins(self):
        reports = [
            ProviderHookReport("claude", ProviderHookSignal.IN_SYNC, "a"),
            ProviderHookReport("codex", ProviderHookSignal.NOT_RENDERED, "b"),
            ProviderHookReport("gemini", ProviderHookSignal.SIDECAR_STALE, "c"),
        ]
        assert worst_hook_signal(reports) is ProviderHookSignal.SIDECAR_STALE

    def test_in_sync_outranks_no_sources(self):
        reports = [
            ProviderHookReport("claude", ProviderHookSignal.NO_SOURCES, "a"),
            ProviderHookReport("codex", ProviderHookSignal.IN_SYNC, "b"),
        ]
        assert worst_hook_signal(reports) is ProviderHookSignal.IN_SYNC

    def test_no_providers_reads_as_nothing_to_render(self):
        assert worst_hook_signal([]) is ProviderHookSignal.NO_SOURCES
