"""Cross-referencing end to end: real ADRs on disk, a real local provider.

The provider is a local HTTP server whose answers are derived from each
request, the way a consistent model would answer: a Choice picks the option
whose text carries the link marker, a pair whose candidate carries it is
judged a link, and a request carrying the blocked marker is refused with the
edge firewall's HTML 403. Every test exercises the real transport, corpus,
engine, service and link writer.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any, cast

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.crossref import (
    REPLY_VERDICTS,
    CrossrefStatus,
    InvalidSourceError,
    VerdictKind,
    crossref_adr,
    crossref_sweep,
    outcome_fields,
    sweep_fields,
)
from vaultspec_core.crossref._engine import max_evaluations
from vaultspec_core.crossref._questions import (
    CHOICE_CHUNK,
    CUT,
    NONE_KEY,
    OPTION_BYTES,
    PAIR_QUESTIONS,
    POOL,
)
from vaultspec_core.search._credential import CREDENTIAL_VARIABLE
from vaultspec_core.search._models import UnavailableReason
from vaultspec_core.search._questions import MODEL
from vaultspec_core.search._transport import JevClient
from vaultspec_core.search.tests.scripted_provider import (
    Received,
    Reply,
    ScriptedProvider,
)
from vaultspec_core.vaultcore.parser import parse_vault_metadata

from .vault import write_adr

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

KEY = "ts-test-4f1c9a2e7b"
ENV = {CREDENTIAL_VARIABLE: KEY}

#: Text a candidate carries when the provider should judge it a link.
LINK = "zebralink"
#: Text the provider's edge refuses.
BLOCKED = "firewalltrip"

SOURCE = "2026-01-01-source-adr"


class Judge:
    """Answer crossref requests from what they contain."""

    def __init__(self) -> None:
        self.errors: list[Exception] = []
        self.choices = 0
        self.pairs = 0

    def __call__(self, received: Received) -> Reply:
        try:
            return self._reply(received)
        except Exception as exc:  # reported by check(), never hidden
            self.errors.append(exc)
            return Reply(status=500, body=b"responder failed")

    def check(self) -> None:
        assert self.errors == []

    def _reply(self, received: Received) -> Reply:
        payload = received.payload()
        state: dict[str, Any] = payload["state"]
        questions: dict[str, dict[str, Any]] = payload["questions"]
        if "candidate" in state:
            self.pairs += 1
            if BLOCKED in state["candidate"]["text"]:
                return Reply.html(403, "<html><body>Attention Required!</body></html>")
            answers = self._pair(state["candidate"]["text"])
        else:
            self.choices += 1
            (qid, question), *_ = questions.items()
            answers = {qid: self._choice(question["criteria"])}
        usage = {"input_tokens": len(received.body) // 4, "output_tokens": 0}
        return Reply.json({"model": MODEL, "answers": answers, "usage": usage})

    @staticmethod
    def _choice(criteria: dict[str, str]) -> dict[str, Any]:
        hits = [key for key, text in criteria.items() if LINK in text]
        probabilities = {key: (0.9 if key in hits else 0.01) for key in criteria}
        if not hits:
            probabilities[NONE_KEY] = 0.9
        choice = max(probabilities, key=lambda key: probabilities[key])
        return {
            "type": "choice",
            "choice": choice,
            "confidence": probabilities[choice],
            "probabilities": probabilities,
        }

    @staticmethod
    def _pair(text: str) -> dict[str, Any]:
        link = LINK in text
        criteria = cast("dict[str, str]", PAIR_QUESTIONS["relation"]["criteria"])
        relations = list(criteria)
        relation = "depends_on" if link else "unrelated"
        return {
            "need": {"type": "noul", "noul": 0.9 if link else 0.1},
            "artifact": {"type": "noul", "noul": 0.8 if link else 0.1},
            "useless": {"type": "noul", "noul": 0.1 if link else 0.9},
            "relation": {
                "type": "choice",
                "choice": relation,
                "confidence": 0.8,
                "probabilities": {
                    r: (0.8 if r == relation else 0.02) for r in relations
                },
            },
        }


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def judge() -> Judge:
    return Judge()


@pytest.fixture
def provider(judge: Judge) -> Generator[ScriptedProvider]:
    with ScriptedProvider(responder=judge) as server:
        yield server
    judge.check()


def _client(provider: ScriptedProvider) -> JevClient:
    return JevClient(KEY, endpoint=provider.endpoint, max_concurrency=4)


def _small_vault(root: Path) -> None:
    """A source, one ADR it should link, one it declares weakly, fillers."""
    write_adr(
        root,
        SOURCE,
        implementation="Writers hold `document_write_lock`.",
        related=("2026-01-03-declared-adr",),
    )
    write_adr(
        root,
        "2026-01-02-governing-adr",
        implementation=f"Every writer takes `document_write_lock`. {LINK}",
    )
    write_adr(root, "2026-01-03-declared-adr", implementation="Unrelated colours.")
    for number in range(4):
        write_adr(root, f"2026-01-1{number}-filler-adr", title=f"filler {number}")


def _related(root: Path, stem: str) -> list[str]:
    text = (root / ".vault" / "adr" / f"{stem}.md").read_text(encoding="utf-8")
    return list(parse_vault_metadata(text)[0].related)


def test_a_small_vault_judges_every_candidate_without_a_choice_stage(
    tmp_path: Path, provider: ScriptedProvider, judge: Judge
) -> None:
    _small_vault(tmp_path)

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.OK
    assert judge.choices == 0
    assert judge.pairs == 6
    kinds = {v.stem: v.kind for v in outcome.verdicts}
    assert kinds == {
        "2026-01-02-governing-adr": VerdictKind.LINK,
        "2026-01-03-declared-adr": VerdictKind.WEAK,
    }
    link = outcome.verdicts[0]
    assert (link.relation, link.declared, link.applied) == ("depends_on", False, False)
    assert outcome.dropped == 4
    assert outcome.bounds is not None
    assert (outcome.bounds.corpus, outcome.bounds.judged) == (7, 6)
    assert outcome.usage is not None
    assert outcome.usage.requests == 6
    # Judging writes nothing.
    assert _related(tmp_path, SOURCE) == ["[[2026-01-03-declared-adr]]"]


def test_a_large_vault_sends_bounded_sanitised_choice_questions(
    tmp_path: Path, provider: ScriptedProvider, judge: Judge
) -> None:
    write_adr(tmp_path, SOURCE, implementation="Uses `graph_cache`.")
    write_adr(
        tmp_path,
        "2026-01-02-governing-adr",
        implementation=f"Owns `graph_cache` and `python -m vaultspec_core`. {LINK}",
    )
    for number in range(60):
        write_adr(
            tmp_path,
            f"2026-02-{number:02d}-filler-adr",
            title="x" * 300,
            implementation="Uses `graph_cache` elsewhere.",
        )

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.OK
    candidates = 61
    assert judge.choices == math.ceil(min(POOL, candidates) / CHOICE_CHUNK)
    assert judge.pairs == CUT
    assert [v.stem for v in outcome.links] == ["2026-01-02-governing-adr"]
    assert outcome.usage is not None
    assert outcome.usage.requests <= max_evaluations()
    for received in provider.received:
        payload = received.payload()
        if "candidate" in payload["state"]:
            continue
        (question,) = payload["questions"].values()
        options = question["criteria"]
        assert len(options) <= CHOICE_CHUNK + 1
        for key, text in options.items():
            assert "`" not in text, key
            assert len(text.encode("utf-8")) <= OPTION_BYTES


def test_apply_writes_new_links_once(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)

    first = crossref_adr(
        tmp_path, SOURCE, apply=True, environ=ENV, client=_client(provider)
    )
    second = crossref_adr(
        tmp_path, SOURCE, apply=True, environ=ENV, client=_client(provider)
    )

    assert first.written == ("2026-01-02-governing-adr",)
    assert second.written == ()
    (again,) = second.links
    assert again.declared
    assert _related(tmp_path, SOURCE) == [
        "[[2026-01-03-declared-adr]]",
        "[[2026-01-02-governing-adr]]",
    ]


def test_a_refused_pair_is_counted_and_the_rest_judged(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-blocked-adr", implementation=BLOCKED)

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.OK
    assert outcome.usage is not None
    assert outcome.usage.unscored == 1
    assert [v.stem for v in outcome.links] == ["2026-01-02-governing-adr"]


def test_every_pair_refused_is_unavailable_not_linkless(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    write_adr(tmp_path, SOURCE)
    write_adr(tmp_path, "2026-01-02-a-adr", implementation=BLOCKED)
    write_adr(tmp_path, "2026-01-03-b-adr", implementation=BLOCKED)

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.UNAVAILABLE
    assert outcome.reason is UnavailableReason.CONTENT_REJECTED
    assert outcome.next_step is not None


def test_without_a_key_nothing_is_sent(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)

    outcome = crossref_adr(tmp_path, SOURCE, environ={}, client=_client(provider))

    assert outcome.status is CrossrefStatus.NOT_CONFIGURED
    assert outcome.next_step is not None
    assert provider.received == []
    fields = outcome_fields(outcome)
    (source,) = cast("list[dict[str, Any]]", fields["sources"])
    assert "remediation" in source
    assert "usage" not in fields


def test_a_rejected_key_fails_the_source(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    rejected = Reply.json({"detail": {"error_type": "authentication_error"}}, 403)

    with ScriptedProvider(rejected) as provider:
        outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.UNAVAILABLE
    assert outcome.reason is UnavailableReason.CREDENTIAL_REJECTED
    assert outcome.verdicts == ()


def test_an_unknown_source_is_refused_before_anything_is_sent(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)

    with pytest.raises(InvalidSourceError):
        crossref_adr(tmp_path, "2026-09-09-nothing-adr", environ=ENV)
    assert provider.received == []


def test_a_sweep_runs_in_stem_order_and_resumes_after_its_cursor(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-retired-adr", status="superseded")

    first = crossref_sweep(
        tmp_path, max_sources=3, environ=ENV, client=_client(provider)
    )
    second = crossref_sweep(
        tmp_path,
        after=first.next_after,
        max_sources=50,
        environ=ENV,
        client=_client(provider),
    )

    governing = [
        "2026-01-01-source-adr",
        "2026-01-02-governing-adr",
        "2026-01-03-declared-adr",
        "2026-01-10-filler-adr",
        "2026-01-11-filler-adr",
        "2026-01-12-filler-adr",
        "2026-01-13-filler-adr",
    ]
    assert [o.source for o in first.outcomes] == governing[:3]
    assert first.next_after == governing[2]
    assert first.remaining == 4
    assert [o.source for o in second.outcomes] == governing[3:]
    assert second.next_after is None
    assert second.remaining == 0


def test_a_sweep_can_take_only_isolated_or_named_adrs(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-retired-adr", status="superseded")

    isolated = crossref_sweep(
        tmp_path, isolated=True, max_sources=50, environ=ENV, client=_client(provider)
    )
    named = crossref_sweep(
        tmp_path,
        ["2026-01-04-retired-adr"],
        environ=ENV,
        client=_client(provider),
    )

    assert SOURCE not in [o.source for o in isolated.outcomes]
    assert "2026-01-04-retired-adr" not in [o.source for o in isolated.outcomes]
    assert [o.source for o in named.outcomes] == ["2026-01-04-retired-adr"]


def test_a_sweep_stops_at_the_first_failed_source(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    limited = Reply.json({"detail": {"error_type": "rate_limited"}}, 429)

    with ScriptedProvider(limited) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_attempts=1)
        sweep = crossref_sweep(tmp_path, max_sources=5, environ=ENV, client=client)

    assert len(sweep.outcomes) == 1
    assert sweep.outcomes[0].reason is UnavailableReason.RATE_LIMITED
    assert sweep.stopped == UnavailableReason.RATE_LIMITED.value
    assert sweep.next_after is None
    assert sweep.remaining == 7


def test_a_sweep_reply_is_bounded(tmp_path: Path, provider: ScriptedProvider) -> None:
    for number in range(12):
        write_adr(
            tmp_path,
            f"2026-03-{number:02d}-linked-adr",
            title="t" * 200,
            implementation=f"Shares `shared_thing`. {LINK}",
        )

    sweep = crossref_sweep(
        tmp_path, max_sources=12, environ=ENV, client=_client(provider)
    )
    fields = sweep_fields(sweep)

    sources = cast("list[dict[str, Any]]", fields["sources"])
    rows = sum(len(source["verdicts"]) for source in sources)
    total = sum(source["verdicts_total"] for source in sources)
    assert total == 12 * 11
    assert rows == REPLY_VERDICTS
    assert any(source["truncated"] for source in sources)
    # Under the envelope's hard ceiling of about 35 KB.
    assert len(json.dumps(fields).encode("utf-8")) < 35_000
