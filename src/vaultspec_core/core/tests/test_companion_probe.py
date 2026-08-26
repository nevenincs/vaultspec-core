"""Tests for the companion-package capability probe.

Every state is reached from fixtures alone: no live companion process, no
network, and no companion package installed. The probe's whole value is that
it is a total local function, so a test suite that needed a running rag would
be evidence the design had failed.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors_companion import (
    RAG_DISTRIBUTION_NAME,
    RAG_HEALTH_AUTHORITY,
    CompanionSignal,
    collect_companion_capability,
)
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps_mode import render_launch_for_mode

if TYPE_CHECKING:
    from pathlib import Path

_MODULE = "vaultspec_rag.server"


def _write_mcp(target: Path, servers: dict[str, object]) -> None:
    """Write an ``.mcp.json`` carrying *servers*."""
    (target / ".mcp.json").write_text(
        json.dumps({"mcpServers": servers}), encoding="utf-8"
    )


def _rag_entry(mode: InstallMode) -> dict[str, object]:
    """Render rag's launch entry for *mode* through core's own comparator.

    Deliberately not a hand-written argv: the probe reads a shape core renders,
    and a literal here would let the fixture and the renderer drift apart while
    the test kept passing.
    """
    command, args = render_launch_for_mode(
        mode, RAG_DISTRIBUTION_NAME, _MODULE, tool_spec=f"{RAG_DISTRIBUTION_NAME}[mcp]"
    )
    return {"command": command, "args": args}


class TestAbsent:
    """No companion entry provisioned."""

    def test_no_mcp_file_is_absent(self, tmp_path: Path):
        cap = collect_companion_capability(tmp_path)
        assert cap.signal is CompanionSignal.ABSENT
        assert cap.mode is None
        assert cap.version is None
        assert not cap.provisioned

    def test_mcp_file_without_rag_entry_is_absent(self, tmp_path: Path):
        _write_mcp(tmp_path, {"vaultspec-core": {"command": "uvx", "args": []}})
        cap = collect_companion_capability(tmp_path)
        assert cap.signal is CompanionSignal.ABSENT

    def test_unreadable_mcp_file_is_absent_not_an_error(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text("{not json", encoding="utf-8")
        cap = collect_companion_capability(tmp_path)
        assert cap.signal is CompanionSignal.ABSENT


class TestDeclared:
    """Entry provisioned, version not resolvable from this environment."""

    @pytest.mark.parametrize("mode", [InstallMode.TOOL, InstallMode.DEPENDENCY])
    def test_entry_present_but_version_invisible(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mode: InstallMode,
    ):
        """The ordinary tool-mode shape: provisioned, version not resolvable.

        The version is forced invisible rather than assumed invisible. rag is
        in core's own ``dev`` dependency group, so it *is* importable in the
        test environment - an assertion that relied on it being absent would
        pass or fail on how the suite happened to be installed.
        """
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(mode)})
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: None,
        )
        cap = collect_companion_capability(tmp_path)
        assert cap.provisioned
        assert cap.signal is CompanionSignal.DECLARED
        assert cap.mode is mode
        assert cap.version is None

    def test_tool_mode_with_extra_still_resolves_its_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """rag's real tool-mode launch names an extra, and must still resolve.

        Regression guard. ``observed_mcp_mode`` re-renders the expected argv
        without a ``tool_spec``, so it expects ``uvx --from vaultspec-rag`` and
        cannot match the ``uvx --from vaultspec-rag[mcp]`` that rag actually
        deploys. Without the structural fallback the most common real rag
        install reports an unknown mode.
        """
        _write_mcp(
            tmp_path,
            {
                RAG_DISTRIBUTION_NAME: {
                    "command": "uvx",
                    "args": ["--from", "vaultspec-rag[mcp]", "python", "-m", _MODULE],
                }
            },
        )
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: None,
        )
        cap = collect_companion_capability(tmp_path)
        assert cap.provisioned
        assert cap.mode is InstallMode.TOOL

    def test_unknown_launcher_leaves_mode_unresolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The fallback degrades to a coarser answer, never a wrong one."""
        _write_mcp(
            tmp_path,
            {RAG_DISTRIBUTION_NAME: {"command": "hand-rolled", "args": []}},
        )
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: None,
        )
        cap = collect_companion_capability(tmp_path)
        assert cap.provisioned
        assert cap.mode is None

    def test_unknown_package_name_is_absent(self, tmp_path: Path):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        cap = collect_companion_capability(tmp_path, package="not-installed-pkg-xyz")
        assert cap.signal is CompanionSignal.ABSENT

    def test_unrecognized_launch_shape_still_counts_as_provisioned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A drifted entry is provisioned-but-unrecognized, never absent."""
        _write_mcp(
            tmp_path,
            {RAG_DISTRIBUTION_NAME: {"command": "hand-rolled", "args": ["whatever"]}},
        )
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: None,
        )
        cap = collect_companion_capability(tmp_path)
        assert cap.provisioned
        assert cap.signal is CompanionSignal.DECLARED
        assert cap.mode is None


class TestFloor:
    """Version resolved, held against core's advisory floor."""

    def test_at_floor_is_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: "0.4.4",
        )
        cap = collect_companion_capability(tmp_path, floor="0.4.4")
        assert cap.signal is CompanionSignal.PRESENT
        assert cap.version == "0.4.4"

    def test_above_floor_is_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: "0.5.0",
        )
        cap = collect_companion_capability(tmp_path, floor="0.4.4")
        assert cap.signal is CompanionSignal.PRESENT

    def test_below_floor_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: "0.3.8",
        )
        cap = collect_companion_capability(tmp_path, floor="0.4.4")
        assert cap.signal is CompanionSignal.BELOW_FLOOR
        assert cap.version == "0.3.8"
        assert cap.floor == "0.4.4"

    def test_unparseable_version_imposes_no_constraint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        monkeypatch.setattr(
            "vaultspec_core.core.diagnosis.collectors_companion._resolve_version",
            lambda _pkg: "not-a-version",
        )
        cap = collect_companion_capability(tmp_path, floor="0.4.4")
        assert cap.signal is CompanionSignal.PRESENT


class TestBoundaries:
    """The probe's design constraints, asserted rather than remembered."""

    def test_never_reports_health(self, tmp_path: Path):
        cap = collect_companion_capability(tmp_path)
        assert cap.reports_health is False
        assert cap.health_authority == RAG_HEALTH_AUTHORITY

    def test_names_the_companion_health_authority(self, tmp_path: Path):
        _write_mcp(tmp_path, {RAG_DISTRIBUTION_NAME: _rag_entry(InstallMode.TOOL)})
        cap = collect_companion_capability(tmp_path)
        assert "doctor" in cap.health_authority

    def test_probe_imports_no_companion_module(self):
        """The probe must not pull a companion package into core's process."""
        import sys

        assert not any(name.startswith("vaultspec_rag") for name in sys.modules)

    def test_probe_module_has_no_network_imports(self):
        """No socket, http, or urllib import anywhere on the probe's path."""
        import inspect

        from vaultspec_core.core.diagnosis import collectors_companion

        source = inspect.getsource(collectors_companion)
        for banned in ("import socket", "import http", "urllib", "requests", "httpx"):
            assert banned not in source, f"probe must not reach the network: {banned}"
