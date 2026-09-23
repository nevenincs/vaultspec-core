"""Vault search end to end: real records on disk, a real local provider.

The provider is a local HTTP server whose answers are derived from each
request it receives, the way a consistent model would answer: a card that
carries the recall marker is chosen in stage one, a block that carries the
answer marker is judged to answer in stage two, and a request that carries the
blocked marker is refused with the edge firewall's HTML 403. Every test
therefore exercises the real transport, the real corpus and the real engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vaultspec_core.search import (
    DEFAULT_RESULTS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    SearchStatus,
    UnavailableReason,
)
from vaultspec_core.search._credential import CREDENTIAL_VARIABLE
from vaultspec_core.search._engine import KIND_QID
from vaultspec_core.search._questions import (
    ANSWERED_THRESHOLD,
    KIND_WEIGHT,
    MODEL,
    NONE_KEY,
)
from vaultspec_core.search._service import search_vault
from vaultspec_core.search._transport import JevClient
from vaultspec_core.vaultcore.blob_hash import git_blob_oid
from vaultspec_core.vaultcore.models import DocType

from .scripted_provider import Received, Reply, ScriptedProvider
from .test_corpus import file_lines, write_record

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from vaultspec_core.search import Excerpt, SearchOutcome

pytestmark = [pytest.mark.unit]

KEY = "ts-test-5b0e93d1c7a2"
ENV = {CREDENTIAL_VARIABLE: KEY}
QUERY = "how is the graph cache kept fresh"

#: Card text the provider recalls in stage one.
RECALL = "recallmark"
#: Block text the provider judges to answer in stage two.
ANSWER = "zebracorn"
#: Block text the provider judges to contradict the query's premise.
REFUTE = "moonquartz"
#: Text the provider's edge refuses.
BLOCKED = "firewalltrip"

FILLER = (
    "This paragraph describes the surrounding context of the decision at some "
    "length, so that it stands as a block of its own. The answering sentence "
    "below it is then excerpted alone rather than folded into a larger block "
    "by the paragraph splitter."
)

CACHE_ADR = f"""\
# `cache` adr: `graph cache` | (**status:** `accepted`)

The graph cache decision {RECALL} keeps every command fast.

## Problem Statement

Rebuilding the graph on every command costs seconds on a large vault.

## Validation detail

{FILLER}

The cache is validated by a {ANSWER} fingerprint of every file before a load.

## Consequences

A stale {ANSWER} entry is rebuilt on the next command.
"""

CACHE_RESEARCH = """\
# `cache` research: `graph cache options`

Measurements of the rebuild cost of the graph.

## Findings

A full rebuild takes three seconds.
"""

OTHER_PLAN = """\
# `other` plan: `unrelated work`

Othermark steps for unrelated work.

## Steps

- S01 do the unrelated thing.
"""


class Judge:
    """Answer Jev requests from what they contain.

    Args:
        kind: The record kind the provider says the query needs.
        spread: Give every stage-one option the same modest probability, so
            every record clears the shortlist floor.
    """

    def __init__(self, *, kind: str = "decision", spread: bool = False) -> None:
        self.kind = kind
        self.spread = spread
        self.errors: list[Exception] = []

    def __call__(self, received: Received) -> Reply:
        try:
            return self._reply(received)
        except Exception as exc:  # reported by check(), never hidden
            self.errors.append(exc)
            return Reply(status=500, body=b"responder failed")

    def check(self) -> None:
        assert self.errors == []

    def _reply(self, received: Received) -> Reply:
        if BLOCKED.encode() in received.body:
            return Reply.html(403, "<html><body>Attention Required!</body></html>")
        payload = received.payload()
        state: dict[str, Any] = payload["state"]
        questions: dict[str, dict[str, Any]] = payload["questions"]
        answers = {
            qid: self._answer(qid, question, state)
            for qid, question in questions.items()
        }
        usage = {"input_tokens": len(received.body) // 4, "output_tokens": 0}
        return Reply.json({"model": MODEL, "answers": answers, "usage": usage})

    def _answer(
        self, qid: str, question: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        if question["type"] == "noul":
            return {"type": "noul", "noul": self._noul(qid, state)}
        options = list(question["criteria"])
        if qid == KIND_QID:
            probabilities = {o: 0.9 if o == self.kind else 0.02 for o in options}
        elif qid == "where":
            probabilities = self._where(options, state["document"]["blocks"])
        else:
            probabilities = self._recall(question["criteria"])
        choice = max(probabilities, key=lambda option: probabilities[option])
        return {
            "type": "choice",
            "choice": choice,
            "confidence": probabilities[choice],
            "probabilities": probabilities,
        }

    def _noul(self, qid: str, state: dict[str, Any]) -> float:
        blocks = state["document"]["blocks"].values()
        text = " ".join(block["text"] for block in blocks)
        if qid == "answers":
            return 0.95 if ANSWER in text else 0.05
        if qid == "about":
            return 0.9 if ANSWER in text else 0.2
        return 0.9 if REFUTE in text else 0.02

    def _recall(self, criteria: dict[str, Any]) -> dict[str, float]:
        records = [key for key in criteria if key != NONE_KEY]
        if self.spread:
            return {**dict.fromkeys(records, 0.1), NONE_KEY: 0.0}
        marked = [key for key in records if RECALL in str(criteria[key])]
        probabilities = {
            key: 0.8 / len(marked) if key in marked else 0.01 for key in records
        }
        probabilities[NONE_KEY] = 0.1 if marked else 0.9
        return probabilities

    @staticmethod
    def _where(options: list[str], blocks: dict[str, Any]) -> dict[str, float]:
        marked = [o for o in options if o in blocks and ANSWER in blocks[o]["text"]]
        if not marked:
            others = [o for o in options if o != NONE_KEY]
            spread = 0.1 / len(others)
            return {**dict.fromkeys(others, spread), NONE_KEY: 0.9}
        probabilities = dict.fromkeys(options, 0.0)
        probabilities[marked[0]] = 0.6
        if len(marked) > 1:
            probabilities[marked[1]] = 0.3
        probabilities[NONE_KEY] = 0.1
        return probabilities


@pytest.fixture
def judge() -> Judge:
    return Judge()


@pytest.fixture
def provider(judge: Judge) -> Iterator[ScriptedProvider]:
    with ScriptedProvider(responder=judge) as server:
        yield server
    judge.check()


@pytest.fixture
def client(provider: ScriptedProvider) -> Iterator[JevClient]:
    with JevClient(KEY, endpoint=provider.endpoint, max_attempts=1) as jev:
        yield jev


def cache_vault(root: Path) -> dict[str, Path]:
    return {
        "adr": write_record(
            root, "adr", "2026-01-02-cache-adr", CACHE_ADR, feature="cache"
        ),
        "research": write_record(
            root,
            "research",
            "2026-01-02-cache-research",
            CACHE_RESEARCH,
            feature="cache",
        ),
        "plan": write_record(
            root,
            "plan",
            "2026-01-03-other-plan",
            OTHER_PLAN,
            feature="other",
            date="2026-01-03",
        ),
    }


def assert_verbatim(path: Path, excerpt: Excerpt | None) -> None:
    assert excerpt is not None
    assert excerpt.text == file_lines(path, excerpt.line_start, excerpt.line_end)


def stage_two(provider: ScriptedProvider) -> list[dict[str, Any]]:
    """The stage-two requests the provider received."""
    payloads = [received.payload() for received in provider.received]
    return [p for p in payloads if "document" in p["state"]]


def search(root: Path, client: JevClient, **kwargs: Any) -> SearchOutcome:
    return search_vault(root, QUERY, environ=ENV, client=client, **kwargs)


class TestRanking:
    def test_answering_record_ranks_first_with_its_excerpt(
        self, tmp_path: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        paths = cache_vault(tmp_path)

        outcome = search(tmp_path, client)

        assert outcome.status is SearchStatus.OK
        assert outcome.query == QUERY
        assert outcome.answered is True
        top = outcome.hits[0]
        assert top.name == "2026-01-02-cache-adr"
        assert top.path == ".vault/adr/2026-01-02-cache-adr.md"
        assert (top.doc_type, top.feature, top.date) == (
            DocType.ADR,
            "cache",
            "2026-01-02",
        )
        assert top.title == "`cache` adr: `graph cache` | (**status:** `accepted`)"
        assert top.answers == pytest.approx(0.95)
        assert top.score == pytest.approx(0.95 + KIND_WEIGHT * 0.9)
        assert top.blob_hash == git_blob_oid(paths["adr"].read_bytes())
        assert top.excerpt is not None
        assert top.excerpt.section == "Validation detail"
        assert top.excerpt.text == (
            f"The cache is validated by a {ANSWER} fingerprint of every file "
            "before a load."
        )
        assert_verbatim(paths["adr"], top.excerpt)
        assert top.supporting is not None
        assert top.supporting.section == "Consequences"
        assert_verbatim(paths["adr"], top.supporting)

    def test_usage_reports_what_the_provider_billed(
        self, tmp_path: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        cache_vault(tmp_path)

        outcome = search(tmp_path, client)

        usage = outcome.usage
        assert usage is not None
        assert usage.model == MODEL
        assert usage.requests == len(provider.received)
        assert usage.input_tokens == sum(len(r.body) // 4 for r in provider.received)
        assert usage.unscored == 0
        assert usage.elapsed_ms > 0

    def test_kind_question_rides_in_one_stage_one_request(
        self, tmp_path: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        cache_vault(tmp_path)

        search(tmp_path, client)

        carrying = [
            r.payload()["questions"]
            for r in provider.received
            if KIND_QID in r.payload()["questions"]
        ]
        assert len(carrying) == 1
        assert len(carrying[0]) > 1

    @pytest.mark.parametrize(
        ("kind", "first"),
        [
            ("decision", "2026-01-02-tie-adr"),
            ("evidence", "2026-01-02-tie-research"),
        ],
    )
    def test_record_kind_breaks_a_tie_between_siblings(
        self, tmp_path: Path, judge: Judge, client: JevClient, kind: str, first: str
    ) -> None:
        body = f"# tie\n\nThe {RECALL} record.\n\n## Detail\n\nIt says {ANSWER}.\n"
        write_record(tmp_path, "adr", "2026-01-02-tie-adr", body, feature="tie")
        write_record(
            tmp_path, "research", "2026-01-02-tie-research", body, feature="tie"
        )
        judge.kind = kind

        outcome = search(tmp_path, client)

        assert [hit.answers for hit in outcome.hits] == [0.95, 0.95]
        assert outcome.hits[0].name == first

    def test_premise_conflict_is_reported_beside_the_score(
        self, tmp_path: Path, client: JevClient
    ) -> None:
        body = (
            f"# refuting adr\n\nThe {RECALL} record.\n\n## Detail\n\n"
            f"It says {ANSWER} and {REFUTE}.\n"
        )
        write_record(tmp_path, "adr", "2026-01-02-refute-adr", body)

        (hit,) = search(tmp_path, client).hits

        assert hit.premise_conflict == pytest.approx(0.9)
        assert hit.score == pytest.approx(hit.answers + KIND_WEIGHT * 0.9)

    def test_nothing_answering_abstains(
        self, tmp_path: Path, client: JevClient
    ) -> None:
        body = f"# quiet\n\nThe {RECALL} record says nothing useful.\n"
        write_record(tmp_path, "adr", "2026-01-02-quiet-adr", body)
        write_record(tmp_path, "plan", "2026-01-02-quiet-plan", body)

        outcome = search(tmp_path, client)

        assert outcome.status is SearchStatus.OK
        assert outcome.answered is False
        assert outcome.hits
        assert all(hit.answers < ANSWERED_THRESHOLD for hit in outcome.hits)


class TestFilters:
    @pytest.mark.parametrize(
        "filters",
        [
            {"feature": "cache"},
            {"doc_types": [DocType.ADR, DocType.RESEARCH]},
            {"date": "2026-01-02"},
        ],
    )
    def test_excluded_records_are_never_sent(
        self,
        tmp_path: Path,
        provider: ScriptedProvider,
        client: JevClient,
        filters: dict[str, Any],
    ) -> None:
        cache_vault(tmp_path)

        outcome = search(tmp_path, client, **filters)

        assert provider.received
        assert all(b"Othermark" not in r.body for r in provider.received)
        assert all(b"other-plan" not in r.body for r in provider.received)
        assert {hit.feature for hit in outcome.hits} == {"cache"}

    def test_nothing_left_after_filtering_sends_nothing(
        self, tmp_path: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        cache_vault(tmp_path)

        outcome = search(tmp_path, client, feature="absent")

        assert outcome.status is SearchStatus.OK
        assert outcome.answered is False
        assert outcome.hits == ()
        assert outcome.window is not None
        assert outcome.window.total == 0
        assert outcome.usage is None
        assert provider.received == []


class TestNotConfigured:
    def test_no_credential_sends_nothing(
        self, tmp_path: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        cache_vault(tmp_path)

        outcome = search_vault(tmp_path, QUERY, environ={}, client=client)

        assert outcome.status is SearchStatus.NOT_CONFIGURED
        assert outcome.query == QUERY
        assert outcome.hits == ()
        assert outcome.usage is None
        assert provider.received == []


class TestUnavailable:
    @pytest.mark.parametrize(
        ("reply", "reason"),
        [
            (
                Reply.json({"detail": {"error_type": "authentication_error"}}, 401),
                UnavailableReason.CREDENTIAL_REJECTED,
            ),
            (Reply.json({"detail": "down"}, 503), UnavailableReason.TRANSPORT),
            (Reply.json({"detail": "slow down"}, 429), UnavailableReason.RATE_LIMITED),
        ],
    )
    def test_provider_failure_returns_no_ranking(
        self, tmp_path: Path, reply: Reply, reason: UnavailableReason
    ) -> None:
        cache_vault(tmp_path)

        with (
            ScriptedProvider(reply) as server,
            JevClient(KEY, endpoint=server.endpoint, max_attempts=1) as jev,
        ):
            outcome = search(tmp_path, jev)

        assert outcome.status is SearchStatus.UNAVAILABLE
        assert outcome.reason is reason
        assert outcome.hits == ()
        assert outcome.answered is False
        assert outcome.window is None
        assert outcome.usage is not None
        assert outcome.usage.requests >= 1

    def test_failure_in_the_full_read_discards_the_recall(self, tmp_path: Path) -> None:
        cache_vault(tmp_path)
        judge = Judge()

        def fail_full_reads(received: Received) -> Reply:
            if b'"document"' in received.body:
                return Reply.json({"detail": "down"}, 500)
            return judge(received)

        with (
            ScriptedProvider(responder=fail_full_reads) as server,
            JevClient(KEY, endpoint=server.endpoint, max_attempts=1) as jev,
        ):
            outcome = search(tmp_path, jev)

        judge.check()
        assert outcome.status is SearchStatus.UNAVAILABLE
        assert outcome.reason is UnavailableReason.TRANSPORT
        assert outcome.hits == ()

    def test_key_no_header_can_carry_is_rejected_unsent(self, tmp_path: Path) -> None:
        cache_vault(tmp_path)

        outcome = search_vault(
            tmp_path, QUERY, environ={CREDENTIAL_VARIABLE: "two words"}
        )

        assert outcome.status is SearchStatus.UNAVAILABLE
        assert outcome.reason is UnavailableReason.CREDENTIAL_REJECTED
        assert outcome.usage is None


class TestContentRejection:
    def test_refused_full_read_leaves_the_record_unscored(
        self, tmp_path: Path, client: JevClient
    ) -> None:
        paths = cache_vault(tmp_path)
        body = (
            f"# blocked adr\n\nThe {RECALL} record.\n\n## Detail\n\n{FILLER}\n\n"
            f"It quotes {BLOCKED} deep in its body.\n"
        )
        write_record(tmp_path, "adr", "2026-01-02-blocked-adr", body, feature="cache")

        outcome = search(tmp_path, client)

        assert outcome.status is SearchStatus.OK
        assert outcome.usage is not None
        assert outcome.usage.unscored == 1
        names = [hit.name for hit in outcome.hits]
        assert "2026-01-02-blocked-adr" not in names
        assert names[0] == "2026-01-02-cache-adr"
        assert_verbatim(paths["adr"], outcome.hits[0].excerpt)

    def test_refused_card_is_isolated_and_the_rest_still_ranked(
        self, tmp_path: Path, client: JevClient
    ) -> None:
        cache_vault(tmp_path)
        write_record(
            tmp_path,
            "adr",
            "2026-01-02-alpha-adr",
            f"# {BLOCKED} alpha\n\nAlpha {RECALL} text.\n",
            feature="cache",
        )
        write_record(
            tmp_path,
            "adr",
            "2026-01-02-beta-adr",
            "# beta\n\nBeta text.\n",
            feature="cache",
        )

        outcome = search(tmp_path, client)

        assert outcome.status is SearchStatus.OK
        assert outcome.usage is not None
        assert outcome.usage.unscored == 1
        top = outcome.hits[0]
        assert top.name == "2026-01-02-cache-adr"
        # The record-kind answer survived the bisection of its request.
        assert top.score == pytest.approx(top.answers + KIND_WEIGHT * 0.9)
        assert "2026-01-02-alpha-adr" not in [hit.name for hit in outcome.hits]


class TestExcerptLines:
    @pytest.mark.parametrize(
        ("newline", "bom"), [("\n", False), ("\r\n", False), ("\n", True)]
    )
    def test_every_excerpt_is_the_file_text_at_its_lines(
        self, tmp_path: Path, client: JevClient, newline: str, bom: bool
    ) -> None:
        body = f"""\
# `lines` adr

The {RECALL} record.

## Code

```python
def f():

    return "{ANSWER}"
```

## Table

| a | b |
| - | - |
| {ANSWER} | 2 |
"""
        path = write_record(
            tmp_path, "adr", "2026-01-02-lines-adr", body, newline=newline, bom=bom
        )

        (hit,) = search(tmp_path, client).hits

        assert hit.excerpt is not None
        assert hit.excerpt.section == "Code"
        assert_verbatim(path, hit.excerpt)
        assert_verbatim(path, hit.supporting)
        assert hit.blob_hash == git_blob_oid(path.read_bytes())


class TestPage:
    @pytest.fixture
    def judge(self) -> Judge:
        return Judge(spread=True)

    @pytest.fixture
    def wide_vault(self, tmp_path: Path) -> Path:
        for doc_type in (DocType.ADR, DocType.RESEARCH, DocType.PLAN):
            for i in range(3):
                write_record(
                    tmp_path,
                    doc_type,
                    f"2026-01-02-r{i}-{doc_type.value}",
                    f"# record {i}\n\nPlain text {i}.\n",
                )
        return tmp_path

    @pytest.mark.parametrize(
        ("limit", "returned"), [(2, 2), (0, DEFAULT_RESULTS), (-3, DEFAULT_RESULTS)]
    )
    def test_page_is_bounded_and_counts_the_rest(
        self,
        wide_vault: Path,
        provider: ScriptedProvider,
        client: JevClient,
        limit: int,
        returned: int,
    ) -> None:
        outcome = search(wide_vault, client, limit=limit)

        judged = len(stage_two(provider))
        assert judged > returned
        assert len(outcome.hits) == returned
        assert outcome.window is not None
        assert outcome.window.total == judged
        assert outcome.window.returned == returned
        assert outcome.window.truncated is True

    def test_limit_is_clamped_to_the_ceiling(
        self, wide_vault: Path, provider: ScriptedProvider, client: JevClient
    ) -> None:
        outcome = search(wide_vault, client, limit=MAX_RESULTS * 10)

        assert outcome.window is not None
        assert outcome.window.total == len(stage_two(provider))
        assert len(outcome.hits) == outcome.window.total <= MAX_RESULTS
        assert outcome.window.truncated is False


class TestQuery:
    @pytest.mark.parametrize("query", ["", "   \n"])
    def test_blank_query_is_refused(self, tmp_path: Path, query: str) -> None:
        with pytest.raises(ValueError, match="blank"):
            search_vault(tmp_path, query, environ=ENV)

    def test_overlong_query_is_refused_before_anything_is_sent(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match=str(MAX_QUERY_CHARS)):
            search_vault(tmp_path, "q" * (MAX_QUERY_CHARS + 1), environ=ENV)
