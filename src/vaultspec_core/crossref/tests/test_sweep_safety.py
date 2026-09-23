"""Sweep safety: cancellation, refusal evidence, refusal runs, selectors, ordering.

A sweep must not keep paying after a failure decides a source, must not read
a provider-wide block as each ADR's own refusal, must stop when refusals run
together, and must refuse a request that names no clear selection.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.crossref import (
    CrossrefStatus,
    InvalidSourceError,
    SweepOutcome,
    crossref_sweep,
)
from vaultspec_core.crossref._engine import _run, order_choice
from vaultspec_core.crossref._questions import MAX_REFUSALS
from vaultspec_core.search._models import UnavailableReason
from vaultspec_core.search._transport import JevClient
from vaultspec_core.search.tests.scripted_provider import Reply, ScriptedProvider

from .test_service import BLOCKED, ENV, KEY, SOURCE, Judge, _small_vault
from .vault import write_adr

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def test_a_failure_in_any_job_cancels_the_jobs_not_yet_started() -> None:
    started: list[int] = []
    lock = threading.Lock()

    def job(number: int) -> Callable[[], int]:
        def run() -> int:
            with lock:
                started.append(number)
            if number == 0:
                time.sleep(1.0)
            if number == 1:
                raise RuntimeError("the provider failed")
            time.sleep(0.05)
            return number

        return run

    with pytest.raises(RuntimeError):
        _run([job(number) for number in range(40)])

    assert len(started) < 40


def test_a_refused_chunk_keeps_its_code_rank_position() -> None:
    pool = ["a", "b", "c", "d", "e"]
    probability = {"a": 0.1, "b": 0.9, "d": 0.5}

    assert order_choice(pool, probability) == ["b", "d", "c", "a", "e"]


def test_a_block_before_the_provider_reads_anything_stops_the_sweep(
    tmp_path: Path,
) -> None:
    _small_vault(tmp_path)
    blocked = Reply.html(403, "<html><body>Attention Required!</body></html>")

    with ScriptedProvider(blocked) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_concurrency=4)
        sweep = crossref_sweep(
            tmp_path, all_adrs=True, max_sources=50, environ=ENV, client=client
        )

    assert len(sweep.outcomes) == MAX_REFUSALS
    assert {o.reason for o in sweep.outcomes} == {UnavailableReason.CONTENT_REJECTED}
    assert sweep.stopped == UnavailableReason.CONTENT_REJECTED.value
    assert sweep.next_after is None
    assert sweep.remaining == 7


def test_a_run_of_refused_adrs_stops_the_sweep(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    for number in range(MAX_REFUSALS + 1):
        write_adr(
            tmp_path, f"2026-01-0{number + 4}-refused-adr", implementation=BLOCKED
        )

    with ScriptedProvider(responder=(judge := Judge())) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_concurrency=4)
        sweep = crossref_sweep(
            tmp_path, all_adrs=True, max_sources=50, environ=ENV, client=client
        )
    judge.check()

    statuses = [o.status for o in sweep.outcomes]
    assert statuses[:3] == [CrossrefStatus.OK] * 3
    assert statuses[3:] == [CrossrefStatus.UNAVAILABLE] * MAX_REFUSALS
    assert sweep.stopped == UnavailableReason.CONTENT_REJECTED.value
    # No refusal in the run was confirmed as its ADR's own, so the cursor
    # stays before the first of them and the next run retries them all.
    assert sweep.next_after == "2026-01-03-declared-adr"


def _sweep(tmp_path: Path, **selection: Any) -> SweepOutcome:
    with ScriptedProvider(responder=(judge := Judge())) as provider:
        client = JevClient(KEY, endpoint=provider.endpoint, max_concurrency=4)
        sweep = crossref_sweep(tmp_path, environ=ENV, client=client, **selection)
    judge.check()
    return sweep


def test_a_resume_that_lands_on_a_refused_adr_moves_past_it(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-refused-adr", implementation=BLOCKED)

    first = _sweep(tmp_path, all_adrs=True, max_sources=3)
    assert first.next_after == "2026-01-03-declared-adr"

    # A one-source sweep lands on the refusal and judges one more to settle it.
    second = _sweep(tmp_path, all_adrs=True, after=first.next_after, max_sources=1)

    assert [o.source for o in second.outcomes] == [
        "2026-01-04-refused-adr",
        "2026-01-10-filler-adr",
    ]
    assert second.stopped is None
    assert second.next_after == "2026-01-10-filler-adr"
    assert second.remaining == 3


def test_a_refusal_no_read_can_settle_stops_the_sweep(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-99-refused-adr", implementation=BLOCKED)

    sweep = _sweep(tmp_path, all_adrs=True, max_sources=50)

    assert sweep.outcomes[-1].reason is UnavailableReason.CONTENT_REJECTED
    assert sweep.stopped == UnavailableReason.CONTENT_REJECTED.value
    assert sweep.remaining == 1
    assert sweep.next_after == "2026-01-13-filler-adr"


def test_a_selection_of_refused_adrs_alone_stops_the_sweep(tmp_path: Path) -> None:
    _small_vault(tmp_path)
    write_adr(tmp_path, "2026-01-04-refused-adr", implementation=BLOCKED)

    sweep = _sweep(tmp_path, refs=["2026-01-04-refused-adr"])

    assert sweep.stopped == UnavailableReason.CONTENT_REJECTED.value
    assert sweep.remaining == 1


def test_a_sweep_settling_refusals_judges_at_most_two_past_its_size(
    tmp_path: Path,
) -> None:
    _small_vault(tmp_path)
    for day in (4, 5, 6):
        write_adr(tmp_path, f"2026-01-0{day}-refused-adr", implementation=BLOCKED)

    sweep = _sweep(tmp_path, all_adrs=True, max_sources=4)

    # Three sources judged OK, the refusal at the size limit, then two more
    # refusals past it: the run reaches the refusal limit and stops there.
    assert len(sweep.outcomes) == 4 + MAX_REFUSALS - 1
    assert sweep.stopped == UnavailableReason.CONTENT_REJECTED.value
    assert sweep.next_after == "2026-01-03-declared-adr"


def test_an_empty_cursor_is_refused(tmp_path: Path) -> None:
    _small_vault(tmp_path)

    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, all_adrs=True, after="", environ=ENV)


def test_a_sweep_needs_one_clear_selector(tmp_path: Path) -> None:
    _small_vault(tmp_path)

    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, environ=ENV)
    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, [SOURCE], all_adrs=True, environ=ENV)
    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, all_adrs=True, isolated=True, environ=ENV)
    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, feature="#", environ=ENV)
