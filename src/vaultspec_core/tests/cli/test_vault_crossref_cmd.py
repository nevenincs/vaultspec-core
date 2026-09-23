"""Tests for ``vaultspec-core vault adr crossref``.

The command-line tests drive the real Typer application against a real
workspace on disk, with the credential chosen through the process environment
the runner passes. None of them reaches the network: without a key nothing is
sent, a refused input ends the command before a client exists, and a key no
HTTP header can carry is refused before any connection opens. The judgment
itself is covered by the crossref package's own tests.

The rendering tests build real outcomes from the crossref package's types and
check what the terminal and ``--json`` carry, including the size of the
worst-case sweep reply.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli.vault_crossref_cmd import _source_lines, _sweep_lines
from vaultspec_core.core.discovery_guidance import LIST_VAULT
from vaultspec_core.core.enums import AdrStatus
from vaultspec_core.crossref import (
    MAX_SOURCES,
    REPLY_VERDICTS,
    Bounds,
    CrossrefOutcome,
    CrossrefStatus,
    CrossrefUsage,
    SweepOutcome,
    Verdict,
    VerdictKind,
    sweep_fields,
)
from vaultspec_core.crossref._questions import CUT, DECLARED_EXTRA, TITLE_CHARS
from vaultspec_core.search import CREDENTIAL_VARIABLE, NextStepKind, UnavailableReason
from vaultspec_core.search.tests.reply_budget import (
    ENVELOPE_BYTES_PER_TOKEN,
    REPLY_CEILING,
)

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

pytestmark = [pytest.mark.integration]

_UNSENDABLE_KEY = "not a sendable key"
_SOURCE = "2026-02-20-widget-adr"


def _workspace(root: Path) -> Path:
    """Build a workspace holding two ADRs."""
    (root / ".vaultspec").mkdir(parents=True)
    for stem in (_SOURCE, "2026-02-21-gadget-adr"):
        adr = root / ".vault" / "adr" / f"{stem}.md"
        adr.parent.mkdir(parents=True, exist_ok=True)
        adr.write_text(
            "---\ntags:\n  - '#adr'\n  - '#widget'\ndate: '2026-02-20'\n---\n\n"
            f"# `widget` adr: `{stem}` | (**status:** `accepted`)\n\n"
            "## Problem Statement\n\nWidgets need a store.\n",
            encoding="utf-8",
        )
    return root


def _crossref(root: Path, *args: str, key: str = "") -> Result:
    runner = CliRunner(
        env={
            "NO_COLOR": "1",
            "TERM": "dumb",
            "COLUMNS": "200",
            CREDENTIAL_VARIABLE: key,
        }
    )
    return runner.invoke(app, ["-t", str(root), "vault", "adr", "crossref", *args])


class TestNotConfigured:
    def test_human_output_names_the_variable_and_the_next_step(
        self, tmp_path: Path
    ) -> None:
        result = _crossref(_workspace(tmp_path), _SOURCE)

        assert result.exit_code == 0, result.output
        assert "not configured" in result.stdout
        assert CREDENTIAL_VARIABLE in result.stdout
        assert f"`{LIST_VAULT} adr`" in result.stdout

    def test_json_envelope_is_skipped_with_the_next_step(self, tmp_path: Path) -> None:
        result = _crossref(_workspace(tmp_path), _SOURCE, "--json")

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "vaultspec.vault.adr.crossref.v1"
        assert envelope["status"] == "skipped"
        (data,) = envelope["data"]["sources"]
        assert data["source"] == _SOURCE
        assert data["status"] == CrossrefStatus.NOT_CONFIGURED
        assert data["verdicts"] == []
        assert data["next_step"] == {
            "kind": NextStepKind.LISTING.value,
            "types": ["adr"],
            "command": f"{LIST_VAULT} adr",
        }
        assert "usage" not in envelope["data"]

    def test_a_sweep_without_a_key_reports_what_remains(self, tmp_path: Path) -> None:
        result = _crossref(_workspace(tmp_path), "--all", "--json")

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)["data"]
        assert data["judged"] == 0
        assert data["remaining"] == 2


class TestRefusedInput:
    def test_no_source_is_refused(self, tmp_path: Path) -> None:
        result = _crossref(_workspace(tmp_path))
        assert result.exit_code == 2

    def test_an_unknown_adr_is_refused(self, tmp_path: Path) -> None:
        result = _crossref(_workspace(tmp_path), "2026-09-09-nothing-adr", key="k")
        assert result.exit_code == 2
        assert "names no ADR" in result.output

    def test_a_sweep_larger_than_the_ceiling_is_refused(self, tmp_path: Path) -> None:
        result = _crossref(
            _workspace(tmp_path), "--all", "--max-sources", str(MAX_SOURCES + 1)
        )
        assert result.exit_code == 2

    def test_an_unsendable_key_fails_without_a_connection(self, tmp_path: Path) -> None:
        result = _crossref(_workspace(tmp_path), _SOURCE, "--json", key=_UNSENDABLE_KEY)

        assert result.exit_code == 1, result.output
        envelope = json.loads(result.stdout)
        assert envelope["status"] == "failed"
        (source,) = envelope["data"]["sources"]
        assert source["reason"] == UnavailableReason.CREDENTIAL_REJECTED


def _verdict(number: int, kind: VerdictKind = VerdictKind.LINK) -> Verdict:
    return Verdict(
        stem=f"2026-09-{number % 28 + 1:02d}-candidate-{number:04d}-adr",
        title="T" * TITLE_CHARS,
        feature="a-reasonably-long-feature-name",
        status=AdrStatus.ACCEPTED,
        kind=kind,
        score=0.61234,
        relation="shared_artifact",
        declared=kind is VerdictKind.WEAK,
        applied=kind is VerdictKind.LINK,
    )


def _judged(source: str, rows: int) -> CrossrefOutcome:
    return CrossrefOutcome(
        source=source,
        status=CrossrefStatus.OK,
        verdicts=tuple(_verdict(i) for i in range(rows)),
        bounds=Bounds(corpus=5_000, pool=192, judged=40, unjudged_declared=("x",)),
        dropped=0,
        usage=CrossrefUsage("jev-1.13.0", 46, 140_000, 4_000, 1),
    )


def test_a_source_renders_its_verdicts_and_what_was_written() -> None:
    outcome = _judged(_SOURCE, 2)

    text = "\n".join(line.text for line in _source_lines(outcome))

    assert f"{_SOURCE}: 2 links" in text
    assert "(written)" in text
    assert "1 declared link(s) not judged" in text


def test_a_stopped_sweep_says_where_to_resume() -> None:
    sweep = SweepOutcome(
        outcomes=(_judged(_SOURCE, 1),),
        remaining=4,
        next_after=_SOURCE,
        stopped=UnavailableReason.RATE_LIMITED.value,
    )

    text = "\n".join(line.text for line in _sweep_lines(sweep))

    assert "stopped early: rate_limited" in text
    assert f"resume with --after {_SOURCE}" in text


def test_the_worst_case_sweep_reply_stays_under_the_ceiling() -> None:
    sources = tuple(
        _judged(f"2026-01-{i % 28 + 1:02d}-source-{i:04d}-adr", CUT + DECLARED_EXTRA)
        for i in range(MAX_SOURCES)
    )
    sweep = SweepOutcome(outcomes=sources, remaining=0)

    fields = sweep_fields(sweep)
    body = json.dumps(fields, ensure_ascii=False).encode("utf-8")

    projected = cast("list[dict[str, list[object]]]", fields["sources"])
    assert sum(len(source["verdicts"]) for source in projected) == REPLY_VERDICTS
    assert len(body) / ENVELOPE_BYTES_PER_TOKEN < REPLY_CEILING
