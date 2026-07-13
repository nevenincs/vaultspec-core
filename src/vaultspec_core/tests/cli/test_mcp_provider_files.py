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

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.workspace_mode import WORKSPACE_FILENAME
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

# The exact MCP-server launch each mode must render into .mcp.json. Asserted
# whole (command plus full args list), never by substring, so a regression in
# either the command or a single arg is caught.
_DEPENDENCY_LAUNCH = {
    "command": "uv",
    "args": ["run", "python", "-m", "vaultspec_core.mcp_server.app"],
}
_TOOL_LAUNCH = {
    "command": "uvx",
    "args": [
        "--from",
        "vaultspec-core",
        "python",
        "-m",
        "vaultspec_core.mcp_server.app",
    ],
}


def _servers(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("mcpServers", {})


def _write_dependency_pyproject(root: Path) -> None:
    """Give *root* a pyproject that declares vaultspec-core as a dependency.

    Dependency mode is only coherent when something can resolve the dependency,
    so an explicit ``--mode dependency`` install requires this to exist.
    """
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["vaultspec-core"]\n',
        encoding="utf-8",
    )


class TestMcpModeRendering:
    def test_dependency_mode_renders_uv_run_launch(self, tmp_path: Path):
        _write_dependency_pyproject(tmp_path)
        WorkspaceFactory(tmp_path).install("all", mode=InstallMode.DEPENDENCY)
        assert _servers(tmp_path / ".mcp.json")["vaultspec-core"] == _DEPENDENCY_LAUNCH

    def test_tool_mode_renders_uvx_launch(self, tmp_path: Path):
        WorkspaceFactory(tmp_path).install("all", mode=InstallMode.TOOL)
        assert _servers(tmp_path / ".mcp.json")["vaultspec-core"] == _TOOL_LAUNCH

    def test_provider_native_config_matches_mode(self, tmp_path: Path):
        """The provider-native MCP config renders the same mode as .mcp.json."""
        WorkspaceFactory(tmp_path).install("all", mode=InstallMode.TOOL)
        agy = tmp_path / ".agents" / "mcp_config.json"
        assert _servers(agy)["vaultspec-core"] == _TOOL_LAUNCH

    def test_absent_declaration_renders_dependency_on_sync(self, tmp_path: Path):
        """The Q6 migration bridge: a workspace whose declaration is absent
        (provisioned before install-mode) must render the dependency launch on
        sync, never silently flip to the uvx tool form.
        """
        factory = WorkspaceFactory(tmp_path).install("all", mode=InstallMode.TOOL)
        assert _servers(tmp_path / ".mcp.json")["vaultspec-core"] == _TOOL_LAUNCH

        # Remove the committed declaration to mimic a legacy, pre-install-mode
        # workspace, then re-sync with --force so the managed entry is rewritten:
        # the render must fall back to the dependency launch.
        (tmp_path / ".vaultspec" / WORKSPACE_FILENAME).unlink()
        factory.sync("all", force=True)
        assert _servers(tmp_path / ".mcp.json")["vaultspec-core"] == _DEPENDENCY_LAUNCH


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
