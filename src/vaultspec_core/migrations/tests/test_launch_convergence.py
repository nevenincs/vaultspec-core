"""Tests for the ``launch_convergence`` registry entry.

Exercises
:func:`vaultspec_core.migrations.m_0_1_48_launch_convergence.migrate`
against real provisioned workspaces: a legacy-shaped managed entry converges
through the fingerprint-verified refresh path, hand-edited entries survive
untouched, a workspace without recorded enrollment is a true no-op, and a
second run after convergence does no work.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps import mcp_sync
from vaultspec_core.migrations.m_0_1_48_launch_convergence import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _bind_context(root: Path) -> None:
    """Point the active workspace context at *root*."""
    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    reset_config()
    init_paths(resolve_workspace(target_override=root))


def _provision(root: Path, mode: InstallMode) -> None:
    """Install core in *mode* and bind the workspace context to *root*."""
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

    if mode in (InstallMode.DEPENDENCY, InstallMode.DEV):
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0"\ndependencies = ["vaultspec-core"]\n',
            encoding="utf-8",
        )
    WorkspaceFactory(root).install("all", mode=mode)
    _bind_context(root)


def _probe_path(root: Path) -> Path:
    return root / ".vaultspec" / "mcps" / "probe.json"


def _write_probe(root: Path, *, args: list[str]) -> None:
    """Write a plain custom MCP definition named ``probe``."""
    _probe_path(root).parent.mkdir(parents=True, exist_ok=True)
    _probe_path(root).write_text(
        json.dumps({"command": "python", "args": args}, indent=2) + "\n",
        encoding="utf-8",
    )


def _servers(root: Path) -> dict[str, dict]:
    raw = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    return raw["mcpServers"]


@pytest.mark.parametrize("mode", [InstallMode.DEPENDENCY, InstallMode.TOOL])
def test_legacy_entry_converges_and_second_run_is_noop(
    tmp_path: Path, mode: InstallMode
) -> None:
    """A managed entry left on an outdated shape converges on migrate; a
    second run reports zero work and mutates nothing, in both render modes."""
    _provision(tmp_path, mode)
    _write_probe(tmp_path, args=["-m", "probe", "--old"])
    mcp_sync(provider="claude")

    # The definition moves on (a newer release renders different bytes); the
    # deployed entry still matches its recorded fingerprint.
    _write_probe(tmp_path, args=["-m", "probe", "--new"])

    result = migrate(tmp_path)

    assert result.counts["refreshed"] >= 1
    assert result.counts["providers"] >= 1
    assert "refreshed" in result.summary
    assert _servers(tmp_path)["probe"]["args"] == ["-m", "probe", "--new"]

    before = (tmp_path / ".mcp.json").read_bytes()
    again = migrate(tmp_path)
    assert again.counts["refreshed"] == 0
    assert "already current" in again.summary
    assert (tmp_path / ".mcp.json").read_bytes() == before


def test_hand_edited_entry_survives_migration(tmp_path: Path) -> None:
    """A managed entry whose bytes no longer match the recorded fingerprint
    is left byte-identical and reported as skipped."""
    _provision(tmp_path, InstallMode.DEPENDENCY)
    _write_probe(tmp_path, args=["-m", "probe", "--old"])
    mcp_sync(provider="claude")

    mcp_path = tmp_path / ".mcp.json"
    raw = json.loads(mcp_path.read_text(encoding="utf-8"))
    raw["mcpServers"]["probe"]["env"] = {"HAND_EDIT": "1"}
    mcp_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    _write_probe(tmp_path, args=["-m", "probe", "--new"])
    before = mcp_path.read_bytes()

    result = migrate(tmp_path)

    assert mcp_path.read_bytes() == before
    assert result.counts["refreshed"] == 0
    assert result.counts["skipped"] >= 1
    assert "left untouched" in result.summary


def test_workspace_without_enrollment_is_true_noop(tmp_path: Path) -> None:
    """No ownership sidecar means nothing to converge: no files appear."""
    result = migrate(tmp_path)

    assert result.counts == {"refreshed": 0, "skipped": 0, "providers": 0}
    assert "nothing to converge" in result.summary
    assert not (tmp_path / ".mcp.json").exists()
    assert not (tmp_path / ".vaultspec").exists()
