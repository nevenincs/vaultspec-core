"""Real-process coverage for the plan mutation transaction boundary."""

from __future__ import annotations

import multiprocessing
from typing import TYPE_CHECKING

from vaultspec_core.plan.mutation_transaction import run_plan_mutation

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event as EventType
    from pathlib import Path


def _hold_transaction(
    plan_path: Path,
    entered: EventType,
    release: EventType,
    finished: EventType,
) -> None:
    def operation() -> None:
        entered.set()
        if not release.wait(timeout=15):
            raise TimeoutError("parent did not release transaction")

    run_plan_mutation(plan_path, dry_run=False, operation=operation)
    finished.set()


def test_plan_mutations_serialize_across_processes(tmp_path: Path) -> None:
    plan_path = tmp_path / ".vault" / "plan" / "example.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan", encoding="utf-8")

    context = multiprocessing.get_context("spawn")
    first_entered = context.Event()
    first_release = context.Event()
    first_finished = context.Event()
    second_entered = context.Event()
    second_release = context.Event()
    second_finished = context.Event()

    first = context.Process(
        target=_hold_transaction,
        args=(plan_path, first_entered, first_release, first_finished),
    )
    second = context.Process(
        target=_hold_transaction,
        args=(plan_path, second_entered, second_release, second_finished),
    )

    first.start()
    assert first_entered.wait(timeout=15)
    second.start()
    assert not second_entered.wait(timeout=1)

    first_release.set()
    assert first_finished.wait(timeout=15)
    assert second_entered.wait(timeout=15)
    second_release.set()
    assert second_finished.wait(timeout=15)

    first.join(timeout=15)
    second.join(timeout=15)
    assert first.exitcode == 0
    assert second.exitcode == 0
