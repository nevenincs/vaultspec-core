"""End-to-end concurrency coverage for owning plan mutation verbs."""

from __future__ import annotations

import random
import subprocess
import sys
from typing import TYPE_CHECKING

from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.tests.plan._factories import make_clean_plan

if TYPE_CHECKING:
    from pathlib import Path



def test_concurrent_cli_step_adds_all_survive(tmp_path: Path) -> None:
    plan_path = tmp_path / ".vault" / "plan" / "concurrent-writers-plan.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        make_clean_plan("L1", rng=random.Random(296), steps=0).render(),
        encoding="utf-8",
    )
    initial_step_count = len(parse_plan(plan_path).steps)
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vaultspec_core",
                "vault",
                "plan",
                "step",
                "add",
                str(plan_path),
                "--action",
                f"record concurrent mutation {index}",
                "--scope",
                f"src/concurrent/{index}.py",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(8)
    ]

    outcomes = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outcomes

    plan = parse_plan(plan_path)
    assert [step.canonical_id for step in plan.steps] == [
        f"S{index:02d}" for index in range(1, initial_step_count + 9)
    ]
    assert {
        step.action
        for step in plan.steps
        if step.action.startswith("record concurrent mutation")
    } == {
        f"record concurrent mutation {index}" for index in range(8)
    }
