"""Tests for the companion-package capability probe.

Every state is reached from real inputs: a real ``.mcp.json`` on disk, a real
installed distribution, and real version strings. No doubles and no runtime
patching - the probe takes its package and floor as parameters precisely so
each state is reachable by choosing them, and a suite that had to patch the
version lookup would be evidence the seam was in the wrong place.

``vaultspec-core`` itself stands in for the companion wherever a
really-installed distribution is needed. It is guaranteed present whenever
this suite runs, which a companion package is not.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.diagnosis.collectors_companion import (
    RAG_DISTRIBUTION_NAME,
    RAG_HEALTH_AUTHORITY,
    CompanionSignal,
    _below_floor,
    collect_companion_capability,
)
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps_mode import render_launch_for_mode

if TYPE_CHECKING:
    from pathlib import Path

_MODULE = "vaultspec_rag.server"

#: A distribution guaranteed installed while this suite runs.
_INSTALLED = "vaultspec-core"

#: A distribution guaranteed *not* installed, so the version axis really
#: resolves to unknown rather than being forced to.
_NOT_INSTALLED = "vaultspec-definitely-not-a-real-distribution"


def _write_mcp(target: Path, servers: dict[str, object]) -> None:
    """Write an ``.mcp.json`` carrying *servers*."""
    (target / ".mcp.json").write_text(
        json.dumps({"mcpServers": servers}), encoding="utf-8"
    )


def _entry(package: str, mode: InstallMode) -> dict[str, object]:
    """Render *package*'s launch entry for *mode* through core's own renderer.

    Deliberately not a hand-written argv: the probe reads a shape core
    renders, and a literal here would let the fixture and the renderer drift
    apart while the test kept passing.
    """
    command, args = render_launch_for_mode(
        mode, package, _MODULE, tool_spec=f"{package}[mcp]"
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

    def test_mcp_file_without_the_entry_is_absent(self, tmp_path: Path):
        _write_mcp(tmp_path, {"some-other-server": {"command": "uvx", "args": []}})
        cap = collect_companion_capability(tmp_path)
        assert cap.signal is CompanionSignal.ABSENT

    def test_unreadable_mcp_file_is_absent_not_an_error(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text("{not json", encoding="utf-8")
        cap = collect_companion_capability(tmp_path)
        assert cap.signal is CompanionSignal.ABSENT

    def test_entry_for_a_different_package_is_absent(self, tmp_path: Path):
        _write_mcp(
            tmp_path,
            {RAG_DISTRIBUTION_NAME: _entry(RAG_DISTRIBUTION_NAME, InstallMode.TOOL)},
        )
        cap = collect_companion_capability(tmp_path, package=_NOT_INSTALLED)
        assert cap.signal is CompanionSignal.ABSENT


class TestDeclared:
    """Entry provisioned, version genuinely unresolvable in this environment."""

    @pytest.mark.parametrize("mode", [InstallMode.TOOL, InstallMode.DEPENDENCY])
    def test_entry_without_an_installed_distribution(
        self, tmp_path: Path, mode: InstallMode
    ):
        """The ordinary tool-mode shape: provisioned, version not visible.

        In tool mode the companion runs through an ephemeral ``uvx --from``
        invocation and never enters the governed project's dependency set, so
        an unresolvable version is the expected state and not a warning.
        """
        _write_mcp(tmp_path, {_NOT_INSTALLED: _entry(_NOT_INSTALLED, mode)})
        cap = collect_companion_capability(tmp_path, package=_NOT_INSTALLED)
        assert cap.provisioned
        assert cap.signal is CompanionSignal.DECLARED
        assert cap.mode is mode
        assert cap.version is None

    def test_tool_mode_with_an_extra_still_resolves_its_mode(self, tmp_path: Path):
        """The companion's real tool-mode launch names an extra.

        Regression guard. ``observed_mcp_mode`` re-renders the expected argv
        without a ``tool_spec``, so it expects ``uvx --from <package>`` and
        cannot match the ``uvx --from <package>[mcp]`` that is actually
        deployed. Without the structural fallback the most common real install
        reports an unknown mode.
        """
        _write_mcp(
            tmp_path,
            {
                _NOT_INSTALLED: {
                    "command": "uvx",
                    "args": [
                        "--from",
                        f"{_NOT_INSTALLED}[mcp]",
                        "python",
                        "-m",
                        _MODULE,
                    ],
                }
            },
        )
        cap = collect_companion_capability(tmp_path, package=_NOT_INSTALLED)
        assert cap.provisioned
        assert cap.mode is InstallMode.TOOL

    def test_unrecognized_launch_shape_still_counts_as_provisioned(
        self, tmp_path: Path
    ):
        """A drifted entry is provisioned-but-unrecognized, never absent."""
        _write_mcp(
            tmp_path, {_NOT_INSTALLED: {"command": "hand-rolled", "args": ["whatever"]}}
        )
        cap = collect_companion_capability(tmp_path, package=_NOT_INSTALLED)
        assert cap.provisioned
        assert cap.signal is CompanionSignal.DECLARED
        assert cap.mode is None


class TestFloor:
    """A really-installed distribution held against a real floor."""

    def test_version_far_below_the_floor_is_flagged(self, tmp_path: Path):
        _write_mcp(tmp_path, {_INSTALLED: _entry(_INSTALLED, InstallMode.TOOL)})
        cap = collect_companion_capability(
            tmp_path, package=_INSTALLED, floor="999.0.0"
        )
        assert cap.signal is CompanionSignal.BELOW_FLOOR
        assert cap.version is not None
        assert cap.floor == "999.0.0"

    def test_version_above_the_floor_is_present(self, tmp_path: Path):
        _write_mcp(tmp_path, {_INSTALLED: _entry(_INSTALLED, InstallMode.TOOL)})
        cap = collect_companion_capability(tmp_path, package=_INSTALLED, floor="0.0.1")
        assert cap.signal is CompanionSignal.PRESENT
        assert cap.version is not None

    def test_version_exactly_at_the_floor_is_present(self, tmp_path: Path):
        """At the floor is not below it."""
        _write_mcp(tmp_path, {_INSTALLED: _entry(_INSTALLED, InstallMode.TOOL)})
        probe = collect_companion_capability(
            tmp_path, package=_INSTALLED, floor="0.0.1"
        )
        assert probe.version is not None
        cap = collect_companion_capability(
            tmp_path, package=_INSTALLED, floor=probe.version
        )
        assert cap.signal is CompanionSignal.PRESENT


class TestFloorComparison:
    """The comparator itself, over real version strings."""

    @pytest.mark.parametrize(
        ("running", "floor"),
        [("0.3.8", "0.4.4"), ("0.4.3", "0.4.4"), ("1.0.0", "1.0.1")],
    )
    def test_below(self, running: str, floor: str):
        assert _below_floor(running, floor) is True

    @pytest.mark.parametrize(
        ("running", "floor"),
        [("0.4.4", "0.4.4"), ("0.5.0", "0.4.4"), ("2.0.0", "1.9.9")],
    )
    def test_not_below(self, running: str, floor: str):
        assert _below_floor(running, floor) is False

    @pytest.mark.parametrize("running", ["not-a-version", "", "unknown", "dev"])
    def test_unparseable_running_version_imposes_no_constraint(self, running: str):
        """Unrecognized version text must never read as below the floor.

        ``parse_version_tuple`` does not raise on a string with no leading
        numeric segment - it returns the empty tuple, which compares below
        every real version. Relying on an exception alone would turn every
        unparseable version into a false below-floor warning, the failure mode
        most corrosive to an advisory nobody is forced to obey.
        """
        assert _below_floor(running, "0.4.4") is False

    @pytest.mark.parametrize("floor", ["not-a-version", "", "unknown"])
    def test_unparseable_floor_imposes_no_constraint(self, floor: str):
        assert _below_floor("0.1.0", floor) is False


class TestBoundaries:
    """The probe's design constraints, asserted rather than remembered."""

    def test_never_reports_health(self, tmp_path: Path):
        cap = collect_companion_capability(tmp_path)
        assert cap.reports_health is False
        assert cap.health_authority == RAG_HEALTH_AUTHORITY

    def test_names_the_companion_health_authority(self, tmp_path: Path):
        _write_mcp(
            tmp_path,
            {RAG_DISTRIBUTION_NAME: _entry(RAG_DISTRIBUTION_NAME, InstallMode.TOOL)},
        )
        cap = collect_companion_capability(tmp_path)
        assert "doctor" in cap.health_authority

    def test_probe_module_has_no_network_imports(self):
        """No socket, http, or urllib import anywhere on the probe's path."""
        import inspect

        from vaultspec_core.core.diagnosis import collectors_companion

        source = inspect.getsource(collectors_companion)
        for banned in ("import socket", "import http", "urllib", "requests", "httpx"):
            assert banned not in source, f"probe must not reach the network: {banned}"

    def test_probe_never_imports_a_companion_module(self, tmp_path: Path):
        """Running the probe must not pull a companion package into core."""
        import sys

        _write_mcp(
            tmp_path,
            {RAG_DISTRIBUTION_NAME: _entry(RAG_DISTRIBUTION_NAME, InstallMode.TOOL)},
        )
        collect_companion_capability(tmp_path)
        assert not any(name.startswith("vaultspec_rag") for name in sys.modules)
