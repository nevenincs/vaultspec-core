"""Per-package MCP render-mode tests for mixed-mode workspaces.

Exercises the invariant that a companion MCP definition (one naming its own
declaring package via ``_vaultspec_mode_package``) renders at *that* package's
own committed render mode during a sync, while core's own token-only definition
renders at the sync-wide mode. Every test drives a real ``install`` plus a real
``mcp_sync`` against on-disk state with the workspace context bound; there are no
test doubles.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps import (
    _MODE_ARGS_TOKEN,
    _MODE_COMMAND_TOKEN,
    _MODE_MODULE_KEY,
    _MODE_PACKAGE_KEY,
    mcp_sync,
    render_launch_for_mode,
)
from vaultspec_core.core.workspace_mode import (
    PackageDeclaration,
    write_package_declaration,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_RAG_PACKAGE = "vaultspec-rag"
_RAG_MODULE = "vaultspec_rag.server"
_CORE_PACKAGE = "vaultspec-core"


def _bind_context(root: Path) -> None:
    """Point the active workspace context at *root* so mcp_sync reads its state."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    reset_config()
    init_paths(resolve_workspace(target_override=root))


def _write_pyproject_with_core_dep(root: Path) -> None:
    """Write a pyproject listing vaultspec-core as a runtime dependency.

    Dependency mode is a declared placement inside a project manifest, so
    provisioning core in that mode needs a ``pyproject.toml`` to resolve against.
    """
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["vaultspec-core"]\n',
        encoding="utf-8",
    )


def _provision(root: Path, core_mode: InstallMode) -> None:
    """Install core in *core_mode* and bind the workspace context to *root*."""
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

    if core_mode in (InstallMode.DEPENDENCY, InstallMode.DEV):
        _write_pyproject_with_core_dep(root)
    WorkspaceFactory(root).install("all", mode=core_mode)
    _bind_context(root)


def _add_companion_definition(root: Path) -> None:
    """Drop a tokenized ``vaultspec-rag`` builtin into the MCP source directory."""
    mcps_dir = root / ".vaultspec" / "mcps"
    mcps_dir.mkdir(parents=True, exist_ok=True)
    definition = {
        "command": _MODE_COMMAND_TOKEN,
        "args": [_MODE_ARGS_TOKEN],
        _MODE_PACKAGE_KEY: _RAG_PACKAGE,
        _MODE_MODULE_KEY: _RAG_MODULE,
    }
    (mcps_dir / f"{_RAG_PACKAGE}.builtin.json").write_text(
        json.dumps(definition, indent=2) + "\n", encoding="utf-8"
    )


def _read_servers(root: Path) -> dict[str, dict]:
    """Return the ``mcpServers`` map from the workspace ``.mcp.json``."""
    raw = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    return raw["mcpServers"]


def _expected_entry(mode: InstallMode, package: str, module: str) -> dict:
    """The launch a package+module renders to at *mode*, derived from the spec."""
    command, args = render_launch_for_mode(mode, package, module)
    return {"command": command, "args": args}


class TestMixedWorkspacePerPackageSync:
    def test_plain_sync_renders_each_entry_at_its_own_mode(
        self, tmp_path: Path
    ) -> None:
        """A mixed workspace syncs core (dependency) and rag (tool) each in its
        own shape, with no false 'differs from definition' SKIP for the sibling."""
        _provision(tmp_path, InstallMode.DEPENDENCY)
        _add_companion_definition(tmp_path)
        write_package_declaration(
            tmp_path, _RAG_PACKAGE, PackageDeclaration(install_mode=InstallMode.TOOL)
        )
        _bind_context(tmp_path)

        result = mcp_sync()

        servers = _read_servers(tmp_path)
        assert servers[_CORE_PACKAGE] == _expected_entry(
            InstallMode.DEPENDENCY,
            _CORE_PACKAGE,
            "vaultspec_core.mcp_server.app",
        )
        assert servers[_RAG_PACKAGE] == _expected_entry(
            InstallMode.TOOL, _RAG_PACKAGE, _RAG_MODULE
        )
        skip_warnings = [w for w in result.warnings if "differs from definition" in w]
        assert skip_warnings == []
        assert not any(action == "[SKIP]" for _name, action in result.items)

    def test_force_sync_does_not_clobber_sibling_to_core_mode(
        self, tmp_path: Path
    ) -> None:
        """--force converges the rag entry against its own tool-mode rendering,
        never core's dependency mode."""
        _provision(tmp_path, InstallMode.DEPENDENCY)
        _add_companion_definition(tmp_path)
        write_package_declaration(
            tmp_path, _RAG_PACKAGE, PackageDeclaration(install_mode=InstallMode.TOOL)
        )
        _bind_context(tmp_path)
        mcp_sync()

        # Corrupt the managed rag entry to core's dependency shape; a renderer
        # that flattened onto core's mode would leave it here under --force.
        mcp_path = tmp_path / ".mcp.json"
        raw = json.loads(mcp_path.read_text(encoding="utf-8"))
        raw["mcpServers"][_RAG_PACKAGE] = _expected_entry(
            InstallMode.DEPENDENCY, _RAG_PACKAGE, _RAG_MODULE
        )
        mcp_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

        mcp_sync(force=True)

        servers = _read_servers(tmp_path)
        assert servers[_RAG_PACKAGE] == _expected_entry(
            InstallMode.TOOL, _RAG_PACKAGE, _RAG_MODULE
        )
        assert servers[_CORE_PACKAGE] == _expected_entry(
            InstallMode.DEPENDENCY,
            _CORE_PACKAGE,
            "vaultspec_core.mcp_server.app",
        )

    def test_legacy_workspace_no_declarations_renders_dependency(
        self, tmp_path: Path
    ) -> None:
        """With no committed declarations, both core and a companion fall through
        the legacy-absent dependency bridge, unchanged from pre-per-package."""
        _provision(tmp_path, InstallMode.DEPENDENCY)
        _add_companion_definition(tmp_path)
        # Remove every committed declaration to model a pre-install-mode workspace.
        (tmp_path / ".vaultspec" / "workspace.json").unlink(missing_ok=True)
        _bind_context(tmp_path)

        result = mcp_sync()

        servers = _read_servers(tmp_path)
        assert servers[_CORE_PACKAGE] == _expected_entry(
            InstallMode.DEPENDENCY,
            _CORE_PACKAGE,
            "vaultspec_core.mcp_server.app",
        )
        assert servers[_RAG_PACKAGE] == _expected_entry(
            InstallMode.DEPENDENCY, _RAG_PACKAGE, _RAG_MODULE
        )
        assert [w for w in result.warnings if "differs from definition" in w] == []


class TestCoreOnlyWorkspaceZeroChurn:
    def test_plain_resync_is_a_no_op(self, tmp_path: Path) -> None:
        """A core-only workspace re-synced immediately after install writes
        nothing new: every entry is unchanged and none is updated or skipped."""
        _provision(tmp_path, InstallMode.DEPENDENCY)
        before = (tmp_path / ".mcp.json").read_text(encoding="utf-8")

        result = mcp_sync()

        after = (tmp_path / ".mcp.json").read_text(encoding="utf-8")
        assert after == before
        assert result.updated == 0
        assert result.added == 0
        assert not any(action == "[SKIP]" for _name, action in result.items)
        servers = _read_servers(tmp_path)
        assert set(servers) == {_CORE_PACKAGE}
