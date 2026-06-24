"""End-to-end tests for provider-native MCP config files.

Antigravity (`agy`) reads MCP servers from `.agents/mcp_config.json` using the
same ``{"mcpServers": {...}}`` schema as the shared workspace ``.mcp.json``.
These tests run real install/sync/uninstall against a temporary workspace and
assert the provider file is written, mirrors the shared server set, tracks
ownership, and preserves user-added entries.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _servers(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("mcpServers", {})


class TestAgyMcpConfig:
    def test_install_writes_agents_mcp_config_mirroring_root(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all")
        agy = tmp_path / ".agents" / "mcp_config.json"
        root = tmp_path / ".mcp.json"
        assert agy.exists(), ".agents/mcp_config.json was not written for agy"
        # agy reads the same schema; the managed server set must match .mcp.json.
        assert _servers(agy) == _servers(root)
        assert "vaultspec-core" in _servers(agy)

    def test_uses_mcpservers_schema_and_managed_sidecar(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all")
        raw = json.loads(
            (tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8")
        )
        assert "mcpServers" in raw
        assert "vaultspec-core" in raw.get("_vaultspecManaged", [])

    def test_not_written_when_antigravity_not_installed(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("claude")
        assert not (tmp_path / ".agents" / "mcp_config.json").exists()

    def test_uninstall_removes_managed_entry(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("all")
        agy = tmp_path / ".agents" / "mcp_config.json"
        assert "vaultspec-core" in _servers(agy)
        factory.uninstall("all")
        if agy.exists():
            assert "vaultspec-core" not in _servers(agy)

    def test_sync_preserves_user_added_agy_server(self, tmp_path: Path):
        factory = WorkspaceFactory(tmp_path).install("all")
        agy = tmp_path / ".agents" / "mcp_config.json"
        raw = json.loads(agy.read_text(encoding="utf-8"))
        raw["mcpServers"]["user-server"] = {"command": "node", "args": ["x.js"]}
        agy.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

        factory.sync("all")
        servers = _servers(agy)
        assert "user-server" in servers, "user-added agy MCP server was dropped"
        assert "vaultspec-core" in servers
