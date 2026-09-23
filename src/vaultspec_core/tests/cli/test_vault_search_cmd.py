"""Tests for ``vaultspec-core vault search``.

The command-line tests drive the real Typer application against a real
workspace on disk, with the credential chosen through the process environment
the runner passes. None of them reaches the network: without a key the
search sends nothing, a filter that excludes every record ends the search
before a client exists, and a key no HTTP header can carry is refused before
any connection opens. The ranking itself is covered by the search package's
own tests.

The rendering tests build real outcomes from the search package's own types
and check what each surface carries: the caps, the truncation markers, the
window, and the keys a caller can derive or already supplied.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli.rendering import TRUNCATE_MARKER
from vaultspec_core.cli.vault_search_cmd import _outcome_lines, _outcome_payload
from vaultspec_core.core.discovery_guidance import SEARCH_ADR
from vaultspec_core.core.windowing import apply_window
from vaultspec_core.search import (
    CREDENTIAL_VARIABLE,
    EXCERPT_CHARS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    PREMISE_CONFLICT_THRESHOLD,
    SUPPORTING_CHARS,
    Excerpt,
    SearchHit,
    SearchOutcome,
    SearchStatus,
)
from vaultspec_core.vaultcore.models import DocType

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

pytestmark = [pytest.mark.integration]

#: A key that no HTTP header can carry, so the search refuses it before any
#: connection opens.
_UNSENDABLE_KEY = "not a sendable key"


def _workspace(root: Path) -> Path:
    """Build a workspace holding one ADR of feature ``widget``."""
    (root / ".vaultspec").mkdir(parents=True)
    adr = root / ".vault" / "adr" / "2026-02-20-widget-adr.md"
    adr.parent.mkdir(parents=True)
    adr.write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#widget'\n"
        "date: '2026-02-20'\n"
        "related: []\n"
        "---\n"
        "\n"
        "# widget adr\n"
        "\n"
        "Widgets are stored in the vault.\n",
        encoding="utf-8",
    )
    return root


def _search(root: Path, *args: str, key: str = "") -> Result:
    """Run ``vault search`` against *root* with *key* as the only credential."""
    runner = CliRunner(env={"NO_COLOR": "1", CREDENTIAL_VARIABLE: key})
    return runner.invoke(app, ["-t", str(root), "vault", "search", *args])


class TestNotConfigured:
    def test_human_output_names_the_variable_and_the_rag_search(
        self, tmp_path: Path
    ) -> None:
        result = _search(_workspace(tmp_path), "why are widgets stored?")

        assert result.exit_code == 0, result.output
        assert "not configured" in result.stdout
        assert CREDENTIAL_VARIABLE in result.stdout
        assert SEARCH_ADR in result.stdout

    def test_json_envelope_is_skipped_with_remediation(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "why are widgets stored?", "--json")

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "vaultspec.vault.search.v1"
        assert envelope["status"] == "skipped"
        data = envelope["data"]
        assert data["status"] == SearchStatus.NOT_CONFIGURED
        assert CREDENTIAL_VARIABLE in data["remediation"]
        assert SEARCH_ADR in data["remediation"]
        # Nothing was ranked, so there is no page to describe.
        assert "hits" not in data
        assert "total" not in data


class TestInputValidation:
    def test_blank_query_is_a_usage_error(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "   ")

        assert result.exit_code == 2
        assert "QUERY" in result.output
        assert "blank" in result.output

    def test_overlong_query_is_a_usage_error(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "q" * (MAX_QUERY_CHARS + 1))

        assert result.exit_code == 2
        assert str(MAX_QUERY_CHARS) in result.output

    def test_longest_query_is_accepted(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "q" * MAX_QUERY_CHARS)

        assert result.exit_code == 0, result.output

    @pytest.mark.parametrize("limit", [0, MAX_RESULTS + 1])
    def test_limit_outside_the_page_ceiling_is_a_usage_error(
        self, tmp_path: Path, limit: int
    ) -> None:
        result = _search(_workspace(tmp_path), "question", "--limit", str(limit))

        assert result.exit_code == 2
        assert "--limit" in result.output

    @pytest.mark.parametrize("limit", [1, MAX_RESULTS])
    def test_limit_at_either_bound_is_accepted(
        self, tmp_path: Path, limit: int
    ) -> None:
        result = _search(_workspace(tmp_path), "question", "--limit", str(limit))

        assert result.exit_code == 0, result.output


class TestTypeFilter:
    def test_generated_indexes_are_not_a_searchable_type(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "question", "--type", "index")

        assert result.exit_code == 2
        assert "--type" in result.output
        assert "index" in result.output

    def test_unknown_type_is_refused(self, tmp_path: Path) -> None:
        result = _search(_workspace(tmp_path), "question", "--type", "memo")

        assert result.exit_code == 2
        assert "memo" in result.output

    def test_several_searchable_types_are_accepted(self, tmp_path: Path) -> None:
        result = _search(
            _workspace(tmp_path), "question", "--type", "adr", "--type", "exec"
        )

        assert result.exit_code == 0, result.output


class TestConfiguredWithoutSending:
    def test_filters_that_exclude_every_record_answer_empty(
        self, tmp_path: Path
    ) -> None:
        result = _search(
            _workspace(tmp_path),
            "why are widgets stored?",
            "--feature",
            "no-such-feature",
            "--json",
            key=_UNSENDABLE_KEY,
        )

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["status"] == "unchanged"
        assert envelope["data"] == {
            "status": "ok",
            "answered": False,
            "hits": [],
            "returned": 0,
            "total": 0,
            "truncated": False,
        }
        assert _UNSENDABLE_KEY not in result.output

    def test_empty_answer_says_nothing_answers(self, tmp_path: Path) -> None:
        result = _search(
            _workspace(tmp_path),
            "why are widgets stored?",
            "--type",
            "plan",
            key=_UNSENDABLE_KEY,
        )

        assert result.exit_code == 0, result.output
        assert "nothing in the vault answers this" in result.stdout
        assert "0 hits" in result.stdout

    def test_unusable_key_fails_without_printing_it(self, tmp_path: Path) -> None:
        result = _search(
            _workspace(tmp_path),
            "why are widgets stored?",
            "--json",
            key=_UNSENDABLE_KEY,
        )

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["status"] == "failed"
        assert envelope["data"]["status"] == SearchStatus.UNAVAILABLE
        assert envelope["data"]["reason"] == "credential_rejected"
        assert CREDENTIAL_VARIABLE in envelope["data"]["remediation"]
        assert _UNSENDABLE_KEY not in result.output

    def test_unusable_key_human_output_names_the_reason(self, tmp_path: Path) -> None:
        result = _search(
            _workspace(tmp_path), "why are widgets stored?", key=_UNSENDABLE_KEY
        )

        assert result.exit_code == 1
        assert "unavailable (credential_rejected)" in result.stdout
        assert _UNSENDABLE_KEY not in result.output


# ---------------------------------------------------------------------------
# Rendering of a ranked page
# ---------------------------------------------------------------------------

#: A passage longer than the excerpt cap, one short line after another, so the
#: clip lands on a line boundary.
_LONG = "\n".join(f"line {n:03d} of the answering passage" for n in range(80))


def _hit(
    rank: int,
    *,
    premise_conflict: float = 0.0,
    excerpt: Excerpt | None = None,
    supporting: Excerpt | None = None,
) -> SearchHit:
    return SearchHit(
        name=f"2026-02-2{rank}-widget-adr",
        path=f".vault/adr/2026-02-2{rank}-widget-adr.md",
        doc_type=DocType.ADR,
        feature="widget",
        date=f"2026-02-2{rank}",
        title=f"widget adr {rank}",
        score=1.0 - rank / 10,
        answers=0.9,
        premise_conflict=premise_conflict,
        excerpt=excerpt,
        supporting=supporting,
        blob_hash="0" * 40,
    )


def _page() -> SearchOutcome:
    """Two shown hits of three ranked; the first has a long and a short excerpt."""
    ranked = [
        _hit(
            1,
            premise_conflict=PREMISE_CONFLICT_THRESHOLD,
            excerpt=Excerpt("Decision > Storage", 12, 91, _LONG),
            supporting=Excerpt("Consequences", 95, 96, "Widgets persist."),
        ),
        _hit(2, premise_conflict=PREMISE_CONFLICT_THRESHOLD - 0.01),
        _hit(3),
    ]
    hits, window = apply_window(ranked, limit=2, pageable=False)
    return SearchOutcome(
        status=SearchStatus.OK,
        query="where are widgets stored?",
        answered=True,
        hits=tuple(hits),
        window=window,
    )


def _page_json() -> dict[str, Any]:
    """The page's ``data`` as a JSON consumer receives it."""
    return json.loads(json.dumps(_outcome_payload(_page())))


class TestJsonPage:
    def test_excerpts_are_clipped_to_their_caps_and_marked(self) -> None:
        first = _page_json()["hits"][0]

        excerpt = first["excerpt"]
        assert len(excerpt["text"]) <= EXCERPT_CHARS < len(_LONG)
        assert _LONG.startswith(excerpt["text"])
        assert _LONG[len(excerpt["text"])] == "\n"
        assert excerpt["truncated"] is True
        assert (excerpt["line_start"], excerpt["line_end"]) == (12, 91)

        supporting = first["supporting"]
        assert len(supporting["text"]) <= SUPPORTING_CHARS
        assert supporting["text"] == "Widgets persist."
        assert supporting["truncated"] is False

    def test_derivable_and_echoed_values_are_left_out(self) -> None:
        data = _page_json()
        hits = data["hits"]

        assert "query" not in data
        assert all("name" not in hit for hit in hits)
        # A hit whose passage was not located has no excerpt key, not a null.
        assert "excerpt" not in hits[1]
        assert "supporting" not in hits[1]

    def test_window_reports_total_and_truncation_without_an_offset(self) -> None:
        data = _page_json()

        assert (data["returned"], data["total"], data["truncated"]) == (2, 3, True)
        assert "next_offset" not in data


class TestHumanPage:
    def test_verdict_leads_and_hit_header_locates_the_passage(self) -> None:
        texts = [line.text for line in _outcome_lines(_page())]

        assert texts[0] == "answered"
        assert texts[1] == (
            "1 2026-02-21-widget-adr adr "
            ".vault/adr/2026-02-21-widget-adr.md:12-91 Decision > Storage"
        )

    def test_premise_note_marks_only_hits_at_the_threshold(self) -> None:
        lines = _outcome_lines(_page())
        notes = [line for line in lines if line.glyph == "!"]

        assert len(notes) == 1
        assert "may contradict an assumption" in notes[0].text
        first_hit = next(
            i for i, line in enumerate(lines) if line.text.startswith("1 ")
        )
        assert lines[first_hit + 1] is notes[0]

    def test_clipped_passage_ends_with_the_truncation_marker(self) -> None:
        texts = [line.text for line in _outcome_lines(_page())]

        also = next(i for i, text in enumerate(texts) if text.startswith("also "))
        assert texts[also - 1] == TRUNCATE_MARKER
        assert texts[also + 1] == "Widgets persist."

    def test_page_ends_with_count_and_what_was_withheld(self) -> None:
        texts = [line.text for line in _outcome_lines(_page())]

        assert texts[-2] == "2 hits"
        assert "1 more hits" in texts[-1]
        assert "--offset" not in texts[-1]
