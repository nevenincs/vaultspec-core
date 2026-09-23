"""Sweep safety: cancellation, refusal evidence, refusal runs, selectors, ordering.

A sweep must not keep paying after a failure decides a source, must not read
a provider-wide block as each ADR's own refusal, must stop when refusals run
together, and must refuse a request that names no clear selection.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.crossref import (
    CrossrefStatus,
    InvalidSourceError,
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

    assert len(sweep.outcomes) == 1
    assert sweep.outcomes[0].reason is UnavailableReason.CONTENT_REJECTED
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
    # The last refusal in the run was not counted as the ADR's own, so the
    # next run starts at it.
    assert sweep.next_after == f"2026-01-0{MAX_REFUSALS + 2}-refused-adr"


def test_a_sweep_needs_one_clear_selector(tmp_path: Path) -> None:
    _small_vault(tmp_path)

    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, environ=ENV)
    with pytest.raises(InvalidSourceError):
        crossref_sweep(tmp_path, [SOURCE], all_adrs=True, environ=ENV)
