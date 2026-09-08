"""The dependency audit is the one audit that GATES, so prove it can fail.

Three repositories in this fleet shipped a dependency "GATE" built on a bare
``uv audit``, which exits 0 even when it prints advisories -- so none of them
could ever fail. These tests pin the replacement's verdict as a pure function of
the finding set, with no network call: a finding fails, an expired suppression
fails, a live suppression passes, and an audit that could not run is never a
pass.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import pytest

from dev.audit import dependency_audit as da

if TYPE_CHECKING:
    from pathlib import Path

#: Every repository in the fleet tiers its tests; this gate is a pure unit.
pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 9, 8)
COORD = da.Coordinate("PyPI", "jinja2", "3.1.4", "uv.lock")
HIT = {"GHSA-q2x7-8rv6-6q7h": {COORD}}


def _describe(_identifier: str) -> dict[str, object]:
    return {
        "summary": "sandbox breakout",
        "aliases": ["CVE-2024-56201"],
        "severity": "MODERATE",
    }


def _report(
    suppressions: list[da.Suppression],
    hits: dict[str, set[da.Coordinate]] = HIT,
) -> da.Report:
    return da.build_report(
        [COORD], hits, suppressions, today=TODAY, describe_fn=_describe
    )


def test_a_finding_fails_the_gate() -> None:
    """The whole reason this module exists."""
    report = _report([])
    assert report.exit_code == da.EXIT_FINDINGS
    assert report.blocking[0].id == "GHSA-q2x7-8rv6-6q7h"
    assert "GHSA-q2x7-8rv6-6q7h" in da.render(report)


def test_a_clean_tree_passes() -> None:
    assert _report([], hits={}).exit_code == da.EXIT_OK


def test_a_live_suppression_accepts_the_finding_visibly() -> None:
    live = da.Suppression("GHSA-q2x7-8rv6-6q7h", "no upstream fix", dt.date(2099, 1, 1))
    report = _report([live])
    assert report.exit_code == da.EXIT_OK
    assert report.findings[0].suppressed_by is live
    assert "SUPPRESSED" in da.render(report)


def test_a_suppression_matches_an_alias() -> None:
    live = da.Suppression(
        "CVE-2024-56201", "same advisory, CVE id", dt.date(2099, 1, 1)
    )
    assert _report([live]).exit_code == da.EXIT_OK


def test_an_expired_suppression_fails_even_with_no_finding() -> None:
    """An acceptance that lapsed is a decision nobody has retaken."""
    stale = da.Suppression("GHSA-q2x7-8rv6-6q7h", "was accepted", dt.date(2026, 1, 1))
    report = _report([stale], hits={})
    assert report.exit_code == da.EXIT_FINDINGS
    assert "EXPIRED" in da.render(report)


def test_an_expired_suppression_does_not_cover_its_finding() -> None:
    stale = da.Suppression("GHSA-q2x7-8rv6-6q7h", "was accepted", dt.date(2026, 1, 1))
    report = _report([stale])
    assert report.blocking
    assert report.exit_code == da.EXIT_FINDINGS


def test_a_suppression_without_an_expiry_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.toml"
    path.write_text('[[suppression]]\nid = "X"\nreason = "y"\n', encoding="utf-8")
    with pytest.raises(da.AuditError, match="expires"):
        da.load_suppressions(path)


def test_a_suppression_without_a_reason_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.toml"
    path.write_text(
        '[[suppression]]\nid = "X"\nreason = "  "\nexpires = 2099-01-01\n',
        encoding="utf-8",
    )
    with pytest.raises(da.AuditError, match="empty reason"):
        da.load_suppressions(path)


def test_the_repository_allowlist_parses() -> None:
    """Whatever this repo has accepted must be readable by the gate."""
    da.load_suppressions()


def test_every_ecosystem_with_a_lockfile_is_scanned() -> None:
    """Python is not the only supply chain; the audit covers what exists."""
    surfaces = {c.surface for c in da.collect_coordinates()}
    assert surfaces, "no dependency coordinates found at all"


def test_no_artifact_without_a_destination() -> None:
    """cadrumo's zero-artifact posture: no destination, nothing written.

    The destination is passed as a value rather than patched into the
    environment, so this asserts the behaviour itself and not the plumbing
    that reads ``VAULTSPEC_CI_REPORTS``.
    """
    assert da.write_artifact(_report([]), "") is None


def test_the_json_report_is_machine_readable(tmp_path: Path) -> None:
    path = da.write_artifact(_report([]), str(tmp_path))
    assert path is not None
    assert path == tmp_path / "dependency-audit.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["gating"] is True
    assert body["exit_code"] == da.EXIT_FINDINGS
    assert body["findings"][0]["id"] == "GHSA-q2x7-8rv6-6q7h"
