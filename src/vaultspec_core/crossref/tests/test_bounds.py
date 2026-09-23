"""The ceilings and the failure paths, end to end against a real local provider.

These tests hold the run to what the decision promises: a source never sends
more than its evaluation ceiling, a slow provider is cut off at the deadline,
a fatal failure stops paying for what is still queued, a refusal leaves only
what it carried unscored, a link that cannot be written is reported rather
than raised, and a sweep's cursor always lets the next run resume.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, cast

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.crossref import (
    CrossrefStatus,
    InvalidSourceError,
    VerdictKind,
    crossref_adr,
    crossref_sweep,
    sweep_fields,
)
from vaultspec_core.crossref._corpus import load_adrs
from vaultspec_core.crossref._engine import Meter, judge, max_evaluations
from vaultspec_core.crossref._prefilter import Index
from vaultspec_core.crossref._questions import (
    CHOICE_CHUNK,
    CUT,
    DECLARED_EXTRA,
    OPTION_BYTES,
    POOL,
)
from vaultspec_core.search._models import UnavailableReason
from vaultspec_core.search._questions import MODEL
from vaultspec_core.search._transport import DeadlineExceededError, JevClient
from vaultspec_core.search.tests.scripted_provider import Reply, ScriptedProvider

from .test_service import BLOCKED, ENV, KEY, LINK, SOURCE, Judge, _small_vault
from .vault import write_adr

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


@pytest.fixture
def judge_answers() -> Judge:
    return Judge()


@pytest.fixture
def provider(judge_answers: Judge) -> Generator[ScriptedProvider]:
    with ScriptedProvider(responder=judge_answers) as server:
        yield server
    judge_answers.check()


def _client(provider: ScriptedProvider) -> JevClient:
    return JevClient(KEY, endpoint=provider.endpoint, max_concurrency=4)


def test_the_worst_case_source_sends_exactly_its_ceiling(
    tmp_path: Path, provider: ScriptedProvider, judge_answers: Judge
) -> None:
    declared = tuple(
        f"2026-04-{number:02d}-declared-adr" for number in range(1, DECLARED_EXTRA + 1)
    )
    write_adr(
        tmp_path,
        SOURCE,
        implementation="Owns `graph_cache` and `VAULTSPEC_GRAPH_CACHE`.",
        related=declared,
    )
    for stem in declared:
        write_adr(tmp_path, stem, title="colour themes", problem="Colours only.")
    wide = "\N{CJK UNIFIED IDEOGRAPH-7F13}" * 400
    for number in range(POOL + 1):
        write_adr(
            tmp_path,
            f"2026-02-{number:03d}-sharer-adr",
            title=wide,
            problem=wide,
            implementation=f"Reads `graph_cache` and `VAULTSPEC_GRAPH_CACHE`. {LINK}",
        )

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.OK
    assert outcome.usage is not None
    assert outcome.usage.requests == max_evaluations()
    assert judge_answers.choices == math.ceil(POOL / CHOICE_CHUNK)
    assert judge_answers.pairs == CUT + DECLARED_EXTRA
    assert outcome.bounds is not None
    assert outcome.bounds.pool == POOL
    weak = {v.stem for v in outcome.verdicts if v.kind is VerdictKind.WEAK}
    assert weak == set(declared)
    for received in provider.received:
        payload = received.payload()
        if "candidate" in payload["state"]:
            continue
        (question,) = payload["questions"].values()
        for text in question["criteria"].values():
            assert len(text.encode("utf-8")) <= OPTION_BYTES


def test_a_slow_provider_is_cut_off_at_the_deadline(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    slow = Reply.json({"model": MODEL, "answers": {}, "usage": {}}, delay=2.0)
    index = Index(load_adrs(tmp_path))

    with ScriptedProvider(slow) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_attempts=1)
        started = time.monotonic()
        with pytest.raises(DeadlineExceededError):
            judge(
                client,
                index.records[SOURCE],
                index,
                deadline=time.monotonic() + 0.5,
                meter=Meter(),
            )
        assert time.monotonic() - started < 2.0


def test_a_refused_choice_chunk_leaves_only_what_it_carried_unscored(
    tmp_path: Path, provider: ScriptedProvider, judge_answers: Judge
) -> None:
    write_adr(tmp_path, SOURCE, implementation="Uses `graph_cache`.")
    write_adr(
        tmp_path,
        "2026-01-02-governing-adr",
        title=f"graph cache {BLOCKED}",
        implementation=f"Owns `graph_cache`. {LINK}",
    )
    for number in range(40):
        write_adr(
            tmp_path,
            f"2026-02-{number:02d}-filler-adr",
            implementation="Mentions `graph_cache` in passing.",
        )

    outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=_client(provider))

    assert outcome.status is CrossrefStatus.OK
    assert judge_answers.choices == 2
    assert outcome.usage is not None
    # The chunk whose options carried the blocked text went unscored; so did
    # the pair of the record that carries it, when the code rank kept it in
    # the cut. Every other request was read.
    assert 1 <= outcome.usage.unscored <= 2
    assert outcome.usage.requests == judge_answers.choices + judge_answers.pairs


def test_a_fatal_failure_cancels_the_evaluations_not_yet_sent(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    for number in range(20):
        write_adr(tmp_path, f"2026-03-{number:02d}-more-adr")
    rejected = Reply.json(
        {"detail": {"error_type": "authentication_error"}}, 403, delay=0.3
    )

    with ScriptedProvider(rejected) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_concurrency=2)
        outcome = crossref_adr(tmp_path, SOURCE, environ=ENV, client=client)

    assert outcome.reason is UnavailableReason.CREDENTIAL_REJECTED
    candidates = 26
    assert len(provider.received) < candidates


def test_a_link_that_cannot_be_written_is_reported_not_raised(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)
    path = tmp_path / ".vault" / "adr" / f"{SOURCE}.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            "related:\n  - '[[2026-01-03-declared-adr]]'",
            "related: '[[2026-01-03-declared-adr]]'",
        ),
        encoding="utf-8",
    )

    sweep = crossref_sweep(
        tmp_path,
        [SOURCE, "2026-01-02-governing-adr"],
        apply=True,
        environ=ENV,
        client=_client(provider),
    )

    first, second = sweep.outcomes
    assert first.status is CrossrefStatus.OK
    assert first.write_failed == ("2026-01-02-governing-adr",)
    assert first.written == ()
    assert second.status is CrossrefStatus.OK
    assert sweep.stopped is None
    source = cast("list[dict[str, Any]]", sweep_fields(sweep)["sources"])[0]
    assert source["write_failed"] == ["2026-01-02-governing-adr"]


def test_a_sweep_moves_past_an_adr_refused_on_its_own_text(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-refused-adr", implementation=BLOCKED)

    sweep = crossref_sweep(
        tmp_path, max_sources=50, environ=ENV, client=_client(provider)
    )

    reasons = {o.source: o.reason for o in sweep.outcomes}
    assert reasons["2026-01-04-refused-adr"] is UnavailableReason.CONTENT_REJECTED
    assert sweep.stopped is None
    assert sweep.remaining == 0
    assert sweep.next_after is None
    assert len(sweep.outcomes) == 8


def test_a_resumed_sweep_that_fails_first_keeps_its_cursor(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    limited = Reply.json({"detail": {"error_type": "rate_limited"}}, 429)

    with ScriptedProvider(limited) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_attempts=1)
        sweep = crossref_sweep(
            tmp_path, after=f"[[{SOURCE}]]", environ=ENV, client=client
        )

    assert sweep.stopped == UnavailableReason.RATE_LIMITED.value
    assert sweep.next_after == SOURCE
    assert sweep.remaining == 6


def test_an_unknown_cursor_and_mixed_selectors_are_refused(
    tmp_path: Path, provider: ScriptedProvider
) -> None:
    _small_vault(tmp_path)

    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, after="2026-09-09-nothing-adr", environ=ENV)
    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, [SOURCE], isolated=True, environ=ENV)
    assert provider.received == []
