"""End-to-end concurrency coverage for owning plan mutation verbs.

Captures are decoded explicitly rather than by the platform's default, and the
failure message carries each child's exit status. Both exist because of how
issue #321 presented, which is worth recording: on the Windows CI runners one
of the eight children intermittently came back with empty output and a
non-zero status, on pull requests that touched nothing this test exercises.

Two things were wrong with the way that arrived.

The capture decoded with :func:`locale.getencoding` - ``cp1252`` on those
runners - because ``text=True`` alone inherits it. The CLI reconfigures its own
stdout to UTF-8 at startup (:func:`vaultspec_core.console.configure_stdio`), so
parent and child disagreed about the encoding of the bytes between them. When
the child emitted a byte cp1252 has no mapping for, ``communicate()`` raised
``UnicodeDecodeError`` on its pipe-reader thread and the captured text was lost
- which is why the evidence arrived empty. ``errors="replace"`` means the bytes
now survive the trip whatever they are.

What produced that byte is *not* established. The one seen in CI was ``0x90``,
which is undefined in cp1252 and invalid as standalone UTF-8, but valid in
cp437 and cp850 - the Windows OEM console codepages. That points at an
OS-level or runtime-level message on a child that died abnormally, rather than
at anything this CLI wrote: no CLI path reachable from these arguments emits a
non-ASCII byte when stdout is a pipe. So the decode fault is very likely a
*secondary* effect that destroyed the diagnosis, not the reason a child failed.

The fix therefore makes the next occurrence legible rather than claiming to
prevent it. If it recurs, the assertion now reports the exit status and the
child's own stderr instead of an empty string, which is the evidence that was
missing the first two times.
"""

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
            encoding="utf-8",
            errors="replace",
        )
        for index in range(8)
    ]

    outcomes = [process.communicate(timeout=30) for process in processes]
    # Report the exit status alongside the streams: a child that dies without
    # writing anything is indistinguishable from a quiet success otherwise,
    # and that ambiguity is what made issue #321 unreadable twice over.
    failures = [
        f"process {index} exited {process.returncode}: "
        f"stdout={stdout!r} stderr={stderr!r}"
        for index, (process, (stdout, stderr)) in enumerate(
            zip(processes, outcomes, strict=True)
        )
        if process.returncode != 0
    ]
    assert not failures, "\n".join(failures)

    plan = parse_plan(plan_path)
    assert [step.canonical_id for step in plan.steps] == [
        f"S{index:02d}" for index in range(1, initial_step_count + 9)
    ]
    assert {
        step.action
        for step in plan.steps
        if step.action.startswith("record concurrent mutation")
    } == {f"record concurrent mutation {index}" for index in range(8)}
