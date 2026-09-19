"""Tests for ``--skip hooks``, the provider-hooks sync pass opt-out.

Two code paths honour the ``hooks`` skip token - the sync pass dispatch in
:func:`vaultspec_core.core.provider_sync._sync_all_providers` and the consent
gate in ``cmd_sync`` - but neither was reachable, because
:func:`vaultspec_core.core.provider_registry.validate_skip` rejected the token
before dispatch ran. These tests pin the token as accepted and prove the pass
it names is the only thing it turns off.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.exceptions import ProviderError
from vaultspec_core.core.provider_registry import validate_skip
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_HOOK_SOURCE = "event: pre_tool_use\nmatcher: run_command\ncommand: echo GUARD\n"


def _write_hook(root: Path) -> None:
    hooks_dir = root / ".vaultspec" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "guard.yaml").write_text(_HOOK_SOURCE, encoding="utf-8")


def _isolate_ledger(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the consent ledger somewhere other than the real operator home.

    The renderer refuses an unapproved hook, so without this a run would
    depend on what the developer executing it happens to have approved.
    """
    from vaultspec_core.triggers import trust

    ledger = root / "operator-home" / ".vaultspec" / trust.TRUST_FILE_NAME
    ledger.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(trust, "trust_file_path", lambda home=None: ledger)


def _approve(root: Path) -> None:
    """Approve every declared hook, as an operator at a terminal would."""
    from vaultspec_core.triggers.trust import grant

    grant(sorted((root / ".vaultspec" / "hooks").glob("*.yaml")))


def _claude_hooks(root: Path) -> dict[str, object]:
    path = root / ".claude" / "settings.json"
    if not path.exists():
        return {}
    settings = json.loads(path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks")
    return hooks if isinstance(hooks, dict) else {}


class TestSkipTokenValidation:
    def test_hooks_is_an_accepted_skip_target(self):
        assert validate_skip({"hooks"}) == {"hooks"}

    def test_hooks_is_accepted_when_core_is_not(self):
        # sync passes allow_core=False; "hooks" must survive that narrowing.
        assert validate_skip({"hooks"}, allow_core=False) == {"hooks"}

    def test_core_is_still_rejected_for_sync(self):
        with pytest.raises(ProviderError, match="core"):
            validate_skip({"core"}, allow_core=False)

    def test_unknown_token_is_still_rejected(self):
        with pytest.raises(ProviderError, match="not-a-component"):
            validate_skip({"not-a-component"})

    def test_error_message_offers_hooks_as_a_valid_target(self):
        with pytest.raises(ProviderError) as excinfo:
            validate_skip({"nonsense"})
        assert "hooks" in str(excinfo.value)


class TestSkipHooksPass:
    def test_sync_renders_provider_hooks_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _isolate_ledger(tmp_path, monkeypatch)
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        _approve(tmp_path)
        factory.sync("all")

        assert "PreToolUse" in _claude_hooks(tmp_path)

    def test_skip_hooks_leaves_provider_hooks_unrendered(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        factory.sync("all", skip={"hooks"})

        assert "PreToolUse" not in _claude_hooks(tmp_path)
        assert not (tmp_path / ".codex" / "hooks.json").exists()
        assert not (tmp_path / ".codex" / ".vaultspec-hooks.json").exists()
        assert not (tmp_path / ".agents" / "hooks.json").exists()

    def test_skip_hooks_still_syncs_the_other_passes(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        factory.sync("all", skip={"hooks"})

        # The rules the ordinary sync owns are still written, so the token
        # turns off one pass rather than the command.
        assert factory.provider_has_rules("claude")

    def test_skip_hooks_does_not_prune_already_rendered_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _isolate_ledger(tmp_path, monkeypatch)
        factory = WorkspaceFactory(tmp_path).install("all")
        _write_hook(tmp_path)
        _approve(tmp_path)
        factory.sync("all")
        assert "PreToolUse" in _claude_hooks(tmp_path)

        # Skipping the pass leaves the previous render in place: the token
        # means "do not reconcile", not "remove".
        factory.sync("all", skip={"hooks"})
        assert "PreToolUse" in _claude_hooks(tmp_path)
