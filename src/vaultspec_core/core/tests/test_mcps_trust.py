"""Exercise executable enrollment consent through the real shared writer."""

from __future__ import annotations

import json
import shutil
import tomllib
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.enums import InstallMode, McpScope, Tool
from vaultspec_core.core.manifest import ManifestData, write_manifest_data
from vaultspec_core.core.mcps_definitions import collect_mcp_servers
from vaultspec_core.core.mcps_mode import render_definition_for_sync
from vaultspec_core.core.mcps_native import normalized_sources
from vaultspec_core.core.mcps_ownership import ownership_path
from vaultspec_core.core.mcps_sync import mcp_sync
from vaultspec_core.core.mcps_targets import resolve_mcp_targets
from vaultspec_core.core.mcps_trust import McpApproval, grant, revoke, trust_file_path
from vaultspec_core.core.tests.test_mcps import _init_context
from vaultspec_core.core.types import SyncResult

pytestmark = pytest.mark.unit


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "repo"
    source = root / ".vaultspec" / "mcps"
    source.mkdir(parents=True)
    (source / "server.builtin.json").write_text(
        json.dumps({"command": "node", "args": ["server.js"], "env": {"A": "1"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    _init_context(root)
    write_manifest_data(
        root, ManifestData(installed={"claude", "antigravity", "codex"})
    )
    yield root
    reset_config()


def capture(
    root: Path,
    provider: Tool,
    scope: McpScope,
    mode: InstallMode = InstallMode.DEPENDENCY,
) -> McpApproval:
    target = resolve_mcp_targets(provider, scope=scope, target_dir=root)[0]
    digests: dict[Path, str] = {}
    sources = collect_mcp_servers(mode=mode, target=root, digests=digests)
    sources = normalized_sources(sources, target, SyncResult())
    path, config = sources["server"]
    return McpApproval.capture(root, target, "server", path, config, digests[path])


def native(root: Path, provider: Tool, scope: McpScope) -> dict[str, Any]:
    target = resolve_mcp_targets(provider, scope=scope, target_dir=root)[0]
    if not target.path.exists():
        return {}
    content = target.path.read_text(encoding="utf-8")
    if provider is Tool.CODEX:
        return tomllib.loads(content).get("mcp_servers", {})
    data = json.loads(content)
    if scope is McpScope.LOCAL:
        return (
            data.get("projects", {})
            .get(root.resolve().as_posix(), {})
            .get("mcpServers", {})
        )
    return data.get("mcpServers", {})


@pytest.mark.parametrize("provider", [Tool.CLAUDE, Tool.ANTIGRAVITY, Tool.CODEX])
@pytest.mark.parametrize("scope", [McpScope.PROJECT, McpScope.USER])
@pytest.mark.parametrize("force", [False, True])
def test_enrollment_requires_exact_grant(
    workspace: Path, provider: Tool, scope: McpScope, force: bool
) -> None:
    result = mcp_sync(provider=provider, scope=scope, force=force)
    if provider is Tool.ANTIGRAVITY and scope is McpScope.USER:
        assert result.errored == 1
        assert native(workspace, Tool.ANTIGRAVITY, McpScope.PROJECT) == {}
        return
    assert result.skipped == 1
    assert result.added == result.updated == 0
    assert "not approved" in result.warnings[0]
    assert native(workspace, provider, scope) == {}
    assert not trust_file_path().exists()
    assert not ownership_path(workspace, scope).exists()
    grant([capture(workspace, provider, scope)])
    assert mcp_sync(provider=provider, scope=scope, force=force).added == 1
    assert native(workspace, provider, scope)["server"]["command"] == "node"
    assert mcp_sync(provider=provider, scope=scope).unchanged == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("command", "attacker"),
        ("args", ["evil.js"]),
        ("env", {"A": "evil"}),
    ],
)
@pytest.mark.parametrize("provider", [Tool.CLAUDE, Tool.CODEX])
def test_changed_definition_cannot_refresh_even_with_force(
    workspace: Path, field: str, value: object, provider: Tool
) -> None:
    grant([capture(workspace, provider, McpScope.PROJECT)])
    assert mcp_sync(provider=provider).added == 1
    before = native(workspace, provider, McpScope.PROJECT)
    source = workspace / ".vaultspec/mcps/server.builtin.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    config[field] = value
    source.write_text(json.dumps(config), encoding="utf-8")
    for force in [False, True]:
        result = mcp_sync(
            provider=provider,
            force=force,
            force_managed=frozenset({"server"}),
            prune=True,
        )
        assert result.skipped == 1
        assert result.updated == result.pruned == 0
        assert native(workspace, provider, McpScope.PROJECT) == before
    grant([capture(workspace, provider, McpScope.PROJECT)])
    assert mcp_sync(provider=provider).updated == 1
    assert native(workspace, provider, McpScope.PROJECT)["server"][field] == value


def test_claude_local_and_scope_provider_binding(workspace: Path) -> None:
    grant([capture(workspace, Tool.CLAUDE, McpScope.LOCAL)])
    assert mcp_sync(provider=Tool.CLAUDE, scope=McpScope.LOCAL).added == 1
    assert mcp_sync(provider=Tool.CLAUDE).skipped == 1
    assert mcp_sync(provider=Tool.CODEX).skipped == 1


def test_raw_bytes_and_shadowing_withdraw_consent(workspace: Path) -> None:
    grant([capture(workspace, Tool.CLAUDE, McpScope.PROJECT)])
    source = workspace / ".vaultspec/mcps/server.builtin.json"
    source.write_bytes(source.read_bytes() + b"\n")
    assert mcp_sync(provider=Tool.CLAUDE).skipped == 1
    grant([capture(workspace, Tool.CLAUDE, McpScope.PROJECT)])
    shutil.copyfile(source, source.with_name("server.json"))
    assert mcp_sync(provider=Tool.CLAUDE, force=True).skipped == 1


@pytest.mark.parametrize(
    "ledger", ["{", "[]", '{"version":2,"grants":{}}', '{"version":true,"grants":{}}']
)
def test_malformed_ledger_denies(workspace: Path, ledger: str) -> None:
    grant([capture(workspace, Tool.CLAUDE, McpScope.PROJECT)])
    trust_file_path().write_text(ledger, encoding="utf-8")
    assert mcp_sync(provider=Tool.CLAUDE, force=True).skipped == 1


def test_forged_repository_ledger_and_copied_checkout_deny(workspace: Path) -> None:
    approval = capture(workspace, Tool.CLAUDE, McpScope.PROJECT)
    forged = {"version": 1, "grants": {approval.key: approval.digest}}
    (workspace / ".vaultspec/mcp-trust.json").write_text(
        json.dumps(forged), encoding="utf-8"
    )
    assert mcp_sync(provider=Tool.CLAUDE, force=True).skipped == 1
    grant([approval])
    other = workspace.parent / "copy"
    shutil.copytree(workspace, other)
    _init_context(other)
    assert mcp_sync(provider=Tool.CLAUDE, force=True).skipped == 1


def test_grant_snapshot_not_later_bytes(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vaultspec_core.core import mcps_definitions

    approval = capture(workspace, Tool.CLAUDE, McpScope.PROJECT)
    source = Path(approval.source)
    approved_bytes = source.read_bytes()
    source.write_text('{"command":"attacker"}', encoding="utf-8")
    original = render_definition_for_sync

    def swap(
        config: dict[str, Any], mode: InstallMode, target: Path | None
    ) -> dict[str, Any]:
        source.write_bytes(approved_bytes)
        return original(config, mode, target)

    monkeypatch.setattr(mcps_definitions, "render_definition_for_sync", swap)
    grant([approval])
    assert mcp_sync(provider=Tool.CLAUDE, force=True).skipped == 1
    assert native(workspace, Tool.CLAUDE, McpScope.PROJECT) == {}


def test_launch_changes_and_revoke_dry_run(workspace: Path) -> None:
    approval = capture(workspace, Tool.CLAUDE, McpScope.PROJECT)
    grant([replace(approval, launch='{"command":"another"}')])
    assert mcp_sync(provider=Tool.CLAUDE).skipped == 1
    grant([approval])
    before = trust_file_path().read_bytes()
    assert mcp_sync(provider=Tool.CLAUDE, dry_run=True).added == 1
    assert native(workspace, Tool.CLAUDE, McpScope.PROJECT) == {}
    assert trust_file_path().read_bytes() == before
    assert revoke(workspace) == 1
    assert mcp_sync(provider=Tool.CLAUDE).skipped == 1


def test_install_mode_change_needs_fresh_grant(workspace: Path) -> None:
    source = workspace / ".vaultspec/mcps/server.builtin.json"
    source.write_text(
        json.dumps(
            {
                "command": "@@VAULTSPEC_INSTALL_MODE_COMMAND@@",
                "args": ["@@VAULTSPEC_INSTALL_MODE_ARGS@@"],
            }
        ),
        encoding="utf-8",
    )
    grant([capture(workspace, Tool.CLAUDE, McpScope.PROJECT)])
    assert mcp_sync(provider=Tool.CLAUDE, mode=InstallMode.DEPENDENCY).added == 1
    before = native(workspace, Tool.CLAUDE, McpScope.PROJECT)
    assert (
        mcp_sync(provider=Tool.CLAUDE, mode=InstallMode.TOOL, force=True).skipped == 1
    )
    assert native(workspace, Tool.CLAUDE, McpScope.PROJECT) == before
    grant([capture(workspace, Tool.CLAUDE, McpScope.PROJECT, InstallMode.TOOL)])
    assert mcp_sync(provider=Tool.CLAUDE, mode=InstallMode.TOOL).updated == 1


@pytest.mark.parametrize("provider", [Tool.CLAUDE, Tool.CODEX])
@pytest.mark.parametrize("withdrawal", ["revoke", "edit"])
def test_consent_refusal_preserves_hand_edit_ownership(
    workspace: Path, provider: Tool, withdrawal: str
) -> None:
    grant([capture(workspace, provider, McpScope.PROJECT)])
    assert mcp_sync(provider=provider).added == 1
    native_target = resolve_mcp_targets(provider, target_dir=workspace)[0].path
    native_target.write_text(
        native_target.read_text(encoding="utf-8").replace('"node"', '"hand-edit"'),
        encoding="utf-8",
    )
    before = ownership_path(workspace, McpScope.PROJECT).read_bytes()
    if withdrawal == "revoke":
        revoke(workspace)
    else:
        source = workspace / ".vaultspec/mcps/server.builtin.json"
        source.write_bytes(source.read_bytes() + b"\n")
    assert mcp_sync(provider=provider).skipped == 1
    assert ownership_path(workspace, McpScope.PROJECT).read_bytes() == before
    grant([capture(workspace, provider, McpScope.PROJECT)])
    assert mcp_sync(provider=provider).skipped == 1
    assert (
        native(workspace, provider, McpScope.PROJECT)["server"]["command"]
        == "hand-edit"
    )
