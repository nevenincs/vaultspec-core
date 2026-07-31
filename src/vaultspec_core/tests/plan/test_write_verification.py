"""Post-write verification for the plan-mutation verbs (issue #296).

A plan verb owns the canonical-identifier guarantee the project's mandate
rests on, so it must never emit a success-shaped result for a mutation the
document did not actually receive. Under concurrency a write can land
partially, be replaced by another writer, or persist text that re-parses into
something other than what was asked; each leaves a wrong state that is
indistinguishable from the right one unless the file is independently
re-read.

These tests drive the two halves of the fix against real files on the real
filesystem: :func:`~vaultspec_core.plan.write_guard.verify_plan_write` turning
a divergence into a typed failure, and the mutation verbs replacing a plan
atomically so a write that cannot complete leaves the previous document whole.
"""

from __future__ import annotations

import os
import random
import stat
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.plan.parser import parse_plan
from vaultspec_core.plan.serialiser import serialise_plan
from vaultspec_core.plan.write_guard import (
    PlanWriteVerificationError,
    verify_plan_write,
)
from vaultspec_core.tests.plan._factories import make_clean_plan

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def runner() -> CliRunner:
    """Typer test runner with colour disabled."""
    return CliRunner(env={"NO_COLOR": "1"})


def _write_plan(
    tmp_path: Path,
    tier: str,
    *,
    seed: int,
    waves: int = 0,
    phases: int = 0,
    steps: int = 0,
) -> Path:
    """Render a clean plan at *tier* onto disk and return its path."""
    spec = make_clean_plan(
        tier,
        rng=random.Random(seed),
        waves=waves,
        phases=phases,
        steps=steps,
    )
    plan_path = tmp_path / f"2026-07-31-verification-{tier.lower()}-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")
    return plan_path


# ---- verify_plan_write, exercised directly ----------------------------------


@pytest.mark.parametrize("tier", ["L1", "L2", "L3", "L4"])
def test_a_faithful_write_verifies_at_every_tier(tmp_path: Path, tier: str) -> None:
    """A document that holds exactly what was serialised passes verification.

    Runs at all four tiers because the container walk verification compares is
    tier-conditional: ``L1`` has Steps only, ``L2`` adds Phases, ``L3`` and
    ``L4`` add Waves.
    """
    plan_path = _write_plan(tmp_path, tier, seed=1, waves=2, phases=2, steps=3)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    text = serialise_plan(plan)
    plan_path.write_text(text, encoding="utf-8")

    verify_plan_write(plan_path, text, plan)


def test_a_document_replaced_after_the_write_fails_verification(
    tmp_path: Path,
) -> None:
    """A concurrent writer's bytes on disk are a hard failure, not a success.

    Reproduces the shape of the reported defect without simulating it: the
    verb's serialised text is what it believes it wrote, and the file holds
    somebody else's document.
    """
    plan_path = _write_plan(tmp_path, "L2", seed=2, phases=2, steps=2)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    intended = serialise_plan(plan)
    plan_path.write_text(intended, encoding="utf-8")

    other = _write_plan(tmp_path, "L1", seed=3, steps=1)
    plan_path.write_text(other.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        verify_plan_write(plan_path, intended, plan)

    assert "does not match the text this mutation wrote" in str(excinfo.value)


def test_a_truncated_document_fails_verification_and_names_the_offset(
    tmp_path: Path,
) -> None:
    """A partially-written document reports where the bytes stopped matching."""
    plan_path = _write_plan(tmp_path, "L1", seed=4, steps=4)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    intended = serialise_plan(plan)
    truncated = intended[: len(intended) // 2]
    plan_path.write_text(truncated, encoding="utf-8")

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        verify_plan_write(plan_path, intended, plan)

    assert f"first diverge at offset {len(truncated)}" in str(excinfo.value)


def test_a_missing_document_fails_verification(tmp_path: Path) -> None:
    """A document that vanished between write and re-read is a hard failure."""
    plan_path = _write_plan(tmp_path, "L1", seed=5, steps=2)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    intended = serialise_plan(plan)
    plan_path.unlink()

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        verify_plan_write(plan_path, intended, plan)

    assert "could not be re-read" in str(excinfo.value)


def test_a_row_that_does_not_survive_the_round_trip_fails_verification(
    tmp_path: Path,
) -> None:
    """Byte-identical text that re-parses differently is still a failed write.

    The row contract reserves ``;`` as the action / scope separator, so an
    action carrying one serialises into a row whose scope clause re-parses as
    the action's tail. The file matches the text the verb wrote, yet the
    document means something other than the mutation that was applied - the
    arm of verification that byte comparison alone cannot reach.
    """
    plan_path = _write_plan(tmp_path, "L1", seed=6, steps=1)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    plan.steps[0].action = "reconcile the ledger; then re-index"
    intended = serialise_plan(plan)
    plan_path.write_text(intended, encoding="utf-8")

    assert plan_path.read_text(encoding="utf-8") == intended

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        verify_plan_write(plan_path, intended, plan)

    assert "does not carry the mutation that was applied" in str(excinfo.value)


def test_a_lost_retirement_ledger_fails_verification(tmp_path: Path) -> None:
    """Retired canonical identifiers must survive the write or the write fails."""
    plan_path = _write_plan(tmp_path, "L1", seed=7, steps=2)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    intended = serialise_plan(plan)
    plan_path.write_text(intended, encoding="utf-8")

    plan.retired_step_ids.add("S09")

    with pytest.raises(PlanWriteVerificationError) as excinfo:
        verify_plan_write(plan_path, intended, plan)

    assert "retirement ledger diverges" in str(excinfo.value)


def test_a_backtick_wrapped_scope_still_verifies(tmp_path: Path) -> None:
    """The row contract's own delimiters are normalisation, not a lost write.

    ``--scope '`src/x.py`'`` reaches disk as the intended scope because the
    serialiser supplies the backticks; verification must not read that
    documented normalisation as a divergence.
    """
    plan_path = _write_plan(tmp_path, "L1", seed=8, steps=1)
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    plan.steps[0].scope = "`src/module/parser.py`"
    intended = serialise_plan(plan)
    plan_path.write_text(intended, encoding="utf-8")

    verify_plan_write(plan_path, intended, plan)


# ---- The CLI mutation verbs -------------------------------------------------


def test_step_add_reports_success_only_for_a_document_that_holds_the_step(
    tmp_path: Path, runner: CliRunner
) -> None:
    """A Step whose row cannot round-trip fails the verb instead of succeeding.

    Before write verification the verb exited 0 and announced the new Step
    while the document carried a row meaning something else - the exact
    silent wrong-state issue #296 reports.
    """
    plan_path = _write_plan(tmp_path, "L2", seed=9, phases=2, steps=2)

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--phase",
            "P01",
            "--action",
            "reconcile the ledger; then re-index",
            "--scope",
            "src/module/parser.py",
        ],
    )

    assert result.exit_code == 1, result.stdout
    combined = result.stdout + (result.stderr or "")
    assert "write verification failed" in combined
    assert "does not carry the mutation that was applied" in combined


def test_step_add_still_applies_and_verifies_an_ordinary_mutation(
    tmp_path: Path, runner: CliRunner
) -> None:
    """The guard is a floor, not a brake: a well-formed Step add still lands."""
    plan_path = _write_plan(tmp_path, "L2", seed=10, phases=2, steps=2)
    before = parse_plan(plan_path.read_text(encoding="utf-8"))

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--phase",
            "P01",
            "--action",
            "reconcile the ledger",
            "--scope",
            "src/module/parser.py",
        ],
    )

    assert result.exit_code == 0, result.stdout
    after = parse_plan(plan_path.read_text(encoding="utf-8"))
    assert len(after.steps) == len(before.steps) + 1
    added = next(s for s in after.steps if s.action == "reconcile the ledger")
    assert added.canonical_id not in {s.canonical_id for s in before.steps}


def test_a_mutation_that_cannot_replace_the_file_leaves_it_whole(
    tmp_path: Path, runner: CliRunner
) -> None:
    """A write that cannot complete must not leave a half-serialised plan.

    Establishes a genuine filesystem condition under which the replacement
    cannot be performed - an open handle on Windows, a read-only parent
    directory elsewhere, the same pair the archive engine's tests use - and
    asserts the previous document survives byte-for-byte. An in-place
    truncate-and-write has no such property: it destroys the old bytes before
    it has the new ones down, which is how issue #296's observation B left a
    document carrying content from the wrong call.
    """
    plan_path = _write_plan(tmp_path, "L2", seed=11, phases=2, steps=2)
    original_bytes = plan_path.read_bytes()
    argv = [
        "vault",
        "plan",
        "step",
        "add",
        str(plan_path),
        "--phase",
        "P01",
        "--action",
        "reconcile the ledger",
        "--scope",
        "src/module/parser.py",
    ]

    if os.name == "nt":
        with plan_path.open("rb"):
            result = runner.invoke(app, argv)
    else:
        original_mode = stat.S_IMODE(plan_path.parent.stat().st_mode)
        plan_path.parent.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            result = runner.invoke(app, argv)
        finally:
            plan_path.parent.chmod(original_mode)

    assert result.exit_code != 0
    assert plan_path.read_bytes() == original_bytes
