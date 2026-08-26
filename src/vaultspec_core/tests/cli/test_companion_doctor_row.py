"""Tests for the semantic-search row on the doctor listing.

The row's whole contract is that it informs without ever acquiring authority:
it must render every companion state, and it must never move the doctor's exit
code. Core has no standing to fail a run over a package it does not depend on.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

import pytest

from vaultspec_core.cli.spec_cmd_doctor import _append_companion_row, doctor_exit_code
from vaultspec_core.core.diagnosis.collectors_companion import (
    RAG_DISTRIBUTION_NAME,
    RAG_HEALTH_AUTHORITY,
    CompanionCapability,
    CompanionSignal,
)
from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
from vaultspec_core.core.diagnosis.signals import FrameworkSignal
from vaultspec_core.core.enums import InstallMode

_ALL_SIGNALS = list(CompanionSignal)


def _capability(
    signal: CompanionSignal,
    version: str | None = "0.4.4",
    mode: InstallMode | None = InstallMode.TOOL,
) -> CompanionCapability:
    return CompanionCapability(
        package=RAG_DISTRIBUTION_NAME,
        signal=signal,
        mode=mode,
        version=version,
        floor="0.4.4",
        health_authority=RAG_HEALTH_AUTHORITY,
    )


def _diagnosis(cap: CompanionCapability | None) -> WorkspaceDiagnosis:
    return WorkspaceDiagnosis(framework=FrameworkSignal.PRESENT, companion=cap)


class TestRowRendering:
    def test_no_probe_result_renders_no_row(self):
        rows: list[dict[str, object]] = []
        _append_companion_row(rows, _diagnosis(None))
        assert rows == []

    @pytest.mark.parametrize("signal", _ALL_SIGNALS)
    def test_every_signal_renders_exactly_one_row(self, signal: CompanionSignal):
        rows: list[dict[str, object]] = []
        _append_companion_row(rows, _diagnosis(_capability(signal)))
        assert len(rows) == 1
        assert rows[0]["component"] == "semantic search"

    @pytest.mark.parametrize("signal", _ALL_SIGNALS)
    def test_no_signal_falls_through_to_a_raw_enum_detail(
        self, signal: CompanionSignal
    ):
        """Every state has authored prose; none leaks its enum repr."""
        rows: list[dict[str, object]] = []
        _append_companion_row(rows, _diagnosis(_capability(signal)))
        assert str(rows[0]["detail"]) != str(signal)

    @pytest.mark.parametrize(
        "signal",
        [CompanionSignal.DECLARED, CompanionSignal.PRESENT],
    )
    def test_provisioned_states_name_the_health_authority(
        self, signal: CompanionSignal
    ):
        """A provisioned-but-dead companion is this design's one blind spot.

        Naming the authority on every provisioned row is what keeps the row
        from reading as a health verdict it never made.
        """
        rows: list[dict[str, object]] = []
        _append_companion_row(rows, _diagnosis(_capability(signal)))
        assert RAG_HEALTH_AUTHORITY in str(rows[0]["detail"])

    def test_below_floor_is_marked_advisory(self):
        rows: list[dict[str, object]] = []
        _append_companion_row(
            rows, _diagnosis(_capability(CompanionSignal.BELOW_FLOOR, version="0.3.8"))
        )
        detail = str(rows[0]["detail"])
        assert "advisory" in detail
        assert "0.3.8" in detail
        assert "0.4.4" in detail

    def test_absent_points_at_the_degraded_path(self):
        rows: list[dict[str, object]] = []
        _append_companion_row(
            rows,
            _diagnosis(_capability(CompanionSignal.ABSENT, version=None, mode=None)),
        )
        assert "find" in str(rows[0]["detail"])

    def test_unresolved_mode_omits_the_mode_clause(self):
        rows: list[dict[str, object]] = []
        _append_companion_row(
            rows, _diagnosis(_capability(CompanionSignal.PRESENT, mode=None))
        )
        detail = str(rows[0]["detail"])
        assert "None mode" not in detail
        assert ", mode" not in detail


class TestExitCodeInvariance:
    """The row informs; it never gains authority over the exit code."""

    @pytest.mark.parametrize("signal", _ALL_SIGNALS)
    def test_companion_state_never_changes_exit_code(self, signal: CompanionSignal):
        baseline = doctor_exit_code(_diagnosis(None))
        assert doctor_exit_code(_diagnosis(_capability(signal))) == baseline

    def test_below_floor_does_not_fail_the_run(self):
        code = doctor_exit_code(
            _diagnosis(_capability(CompanionSignal.BELOW_FLOOR, version="0.1.0"))
        )
        assert code == doctor_exit_code(_diagnosis(None))
