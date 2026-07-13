"""Tests for the mode-flip MCP force-gate fix on ``install --upgrade``.

These exercise the ``mode-flip-force-asymmetry`` audit finding: on an upgrade
that flips the workspace's install mode, the pre-commit and declaration
renderers rewrite unconditionally, but the MCP sync is force-gated and would
leave a pre-existing managed ``vaultspec-core`` entry stranded in the old
mode's launch shape until a later forced re-sync. The fix forces just that
managed entry when a flip is detected, keeping the migration atomic across the
three renderers while leaving same-mode divergence, foreign entries, and
non-flip upgrades on their existing semantics.

Every test drives a real ``install_run`` over a real filesystem through
:class:`WorkspaceFactory`; there are no test doubles.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors import collect_mode_mismatch_state
from vaultspec_core.core.diagnosis.signals import ModeMismatchSignal
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps import _MODE_MCP_LAUNCH
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_DEPENDENCY_COMMAND, _DEPENDENCY_ARGS = _MODE_MCP_LAUNCH[InstallMode.DEPENDENCY]
_TOOL_COMMAND, _TOOL_ARGS = _MODE_MCP_LAUNCH[InstallMode.TOOL]


def _write_pyproject_with_vaultspec(root: Path) -> None:
    """Write a ``pyproject.toml`` listing ``vaultspec-core`` as a dependency."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["vaultspec-core"]\n',
        encoding="utf-8",
    )


def _read_mcp(root: Path) -> dict:
    """Read the parsed ``.mcp.json`` for *root*."""
    return json.loads((root / ".mcp.json").read_text(encoding="utf-8"))


def _vaultspec_entry(root: Path) -> dict:
    """Return the ``vaultspec-core`` server entry from ``.mcp.json``."""
    return _read_mcp(root)["mcpServers"]["vaultspec-core"]


def _make_legacy_flip_workspace(root: Path) -> None:
    """Provision a dependency-mode workspace, then strip it to a legacy flip.

    Installs real dependency-mode artifacts (a ``uv run`` MCP launch and hook
    entries), then deletes both the committed mode declaration and the
    ``pyproject.toml`` dependency evidence. A subsequent bare ``install
    --upgrade`` therefore has no declaration to honor and no dependency
    evidence to detect, so it infers tool mode against dependency-shaped
    artifacts: the exact bare-upgrade mode flip the audit describes.
    """
    _write_pyproject_with_vaultspec(root)
    WorkspaceFactory(root).install("all", mode=InstallMode.DEPENDENCY)
    (root / ".vaultspec" / "workspace.json").unlink()
    (root / "pyproject.toml").unlink()


class TestModeFlipForcesManagedEntry:
    def test_flip_upgrade_rewrites_stale_managed_entry_without_force(
        self, tmp_path: Path
    ) -> None:
        """A bare mode-flip upgrade rewrites the stale managed MCP entry in the
        same run without ``--force``, leaving the workspace mode-coherent.
        """
        _make_legacy_flip_workspace(tmp_path)

        # Precondition: the deployed MCP launch is still the old dependency
        # shape and disagrees with the tool mode the upgrade will infer.
        before = _vaultspec_entry(tmp_path)
        assert before["command"] == _DEPENDENCY_COMMAND
        assert before["args"] == list(_DEPENDENCY_ARGS)

        WorkspaceFactory(tmp_path).install("all", upgrade=True)

        after = _vaultspec_entry(tmp_path)
        assert after["command"] == _TOOL_COMMAND
        assert after["args"] == list(_TOOL_ARGS)
        # All three renderers migrated atomically: declaration, hooks, and the
        # MCP launch now agree on tool mode.
        assert collect_mode_mismatch_state(tmp_path) == ModeMismatchSignal.CLEAN

    def test_same_mode_divergent_managed_entry_is_preserved_without_force(
        self, tmp_path: Path
    ) -> None:
        """A managed entry that diverges but stays in the declared mode keeps
        today's force-gated semantics on a non-flip upgrade: it is skipped and
        preserved, not clobbered by the flip force path.
        """
        WorkspaceFactory(tmp_path).install("all", mode=InstallMode.TOOL)

        # Diverge the managed entry without changing its mode shape: the
        # command and args still name tool mode, so no flip is detected, but an
        # extra field makes it differ from its rendered source definition.
        mcp = _read_mcp(tmp_path)
        mcp["mcpServers"]["vaultspec-core"]["env"] = {"HAND_ALTERED": "1"}
        (tmp_path / ".mcp.json").write_text(
            json.dumps(mcp, indent=2) + "\n", encoding="utf-8"
        )

        WorkspaceFactory(tmp_path).install("all", upgrade=True)

        after = _vaultspec_entry(tmp_path)
        # Force-gate untouched: the divergent managed entry survives verbatim.
        assert after.get("env") == {"HAND_ALTERED": "1"}
        assert after["command"] == _TOOL_COMMAND

    def test_flip_upgrade_leaves_foreign_user_entry_untouched(
        self, tmp_path: Path
    ) -> None:
        """The flip force is scoped to the managed ``vaultspec-core`` entry: a
        user-owned MCP entry present during a flip upgrade is left byte-for-byte
        intact while the managed entry migrates.
        """
        _make_legacy_flip_workspace(tmp_path)
        WorkspaceFactory(tmp_path).add_user_mcp_servers()
        foreign_before = _read_mcp(tmp_path)["mcpServers"]["my-custom-server"]

        WorkspaceFactory(tmp_path).install("all", upgrade=True)

        after = _read_mcp(tmp_path)
        # Foreign entry untouched; managed entry migrated to the new mode.
        assert after["mcpServers"]["my-custom-server"] == foreign_before
        assert after["mcpServers"]["vaultspec-core"]["command"] == _TOOL_COMMAND

    def test_non_flip_upgrade_takes_no_force_path(self, tmp_path: Path) -> None:
        """A non-flip upgrade never engages the force path: a divergent
        user-owned entry and the already-matching managed entry both survive an
        upgrade unchanged.
        """
        WorkspaceFactory(tmp_path).install("all", mode=InstallMode.TOOL)

        # A user-owned entry that intentionally diverges from what any managed
        # source would render; it must be untouched by the upgrade.
        mcp = _read_mcp(tmp_path)
        mcp["mcpServers"]["my-custom-server"] = {
            "command": "node",
            "args": ["server.js"],
            "env": {"DIVERGENT": "1"},
        }
        (tmp_path / ".mcp.json").write_text(
            json.dumps(mcp, indent=2) + "\n", encoding="utf-8"
        )
        foreign_before = _read_mcp(tmp_path)["mcpServers"]["my-custom-server"]
        managed_before = _vaultspec_entry(tmp_path)

        WorkspaceFactory(tmp_path).install("all", upgrade=True)

        after = _read_mcp(tmp_path)
        assert after["mcpServers"]["my-custom-server"] == foreign_before
        assert after["mcpServers"]["vaultspec-core"] == managed_before
