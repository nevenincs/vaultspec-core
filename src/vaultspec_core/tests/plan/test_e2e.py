"""End-to-end smoke test for the ``vault plan`` CLI surface.

Exercises the full lifecycle of a plan document through the Typer
runner: create from factory, write to disk, run ``status``, run
``check``, run ``query``, toggle a Step, and re-validate via
``check`` after the toggle. Asserts every command exits cleanly and
that the round-trip preserves canonical identifiers.
"""

from __future__ import annotations

import random

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.plan._factories import make_clean_plan


@pytest.fixture()
def runner() -> CliRunner:
    """Typer test runner with colour disabled."""
    return CliRunner(env={"NO_COLOR": "1"})


def test_status_command_reports_clean_plan(tmp_path, runner: CliRunner) -> None:
    """``vault plan status`` exits cleanly and reports the declared tier."""
    rng = random.Random(0)
    spec = make_clean_plan("L2", rng=rng, phases=2, steps=3)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "status", str(plan_path)])

    assert result.exit_code == 0, result.stdout
    assert "Tier: L2" in result.stdout
    assert "Steps" in result.stdout


def test_status_json_output_is_valid_json(tmp_path, runner: CliRunner) -> None:
    """``vault plan status --json`` emits a parseable payload."""
    import json

    rng = random.Random(1)
    spec = make_clean_plan("L3", rng=rng, waves=1, phases=2, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "status", str(plan_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["tier"] == "L3"
    assert payload["wave_count"] == 1


def test_check_command_clean_plan_exits_zero(tmp_path, runner: CliRunner) -> None:
    """``vault plan check`` on a clean plan exits with status 0."""
    rng = random.Random(2)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "check", str(plan_path)])

    assert result.exit_code == 0


def test_step_check_toggles_persistence_to_disk(tmp_path, runner: CliRunner) -> None:
    """``vault plan step check`` mutates the file on disk; round-trip preserves ids."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(3)
    spec = make_clean_plan("L1", rng=rng, steps=3)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app, ["vault", "plan", "step", "check", str(plan_path), "S02"]
    )

    assert result.exit_code == 0
    plan = parse_plan(plan_path)
    target = next(s for s in plan.steps if s.canonical_id == "S02")
    assert target.checked is True
    untouched = next(s for s in plan.steps if s.canonical_id == "S01")
    assert untouched.checked is False


def test_query_open_filter_lists_uncompleted_steps(tmp_path, runner: CliRunner) -> None:
    """``vault plan query --open`` lists every open Step in the plan."""
    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    spec.steps[0].checked = True
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "query", str(plan_path), "--open"])

    assert result.exit_code == 0
    assert "Matched 3 of 4" in result.stdout


def test_tier_show_reports_canonical_tier(tmp_path, runner: CliRunner) -> None:
    """``vault plan tier show`` prints the declared tier."""
    rng = random.Random(5)
    spec = make_clean_plan("L4", rng=rng, waves=1, phases=1, steps=1)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "tier", "show", str(plan_path)])

    assert result.exit_code == 0
    assert "L4" in result.stdout


def test_help_lists_plan_subcommands(runner: CliRunner) -> None:
    """``vault plan --help`` lists every documented subcommand group."""
    result = runner.invoke(app, ["vault", "plan", "--help"])

    assert result.exit_code == 0
    output = result.stdout
    for verb in ("status", "check", "query", "step", "phase", "wave", "epic", "tier"):
        assert verb in output, f"help text missing {verb!r}: {output}"


def test_step_add_appends_new_canonical_id(tmp_path, runner: CliRunner) -> None:
    """``vault plan step add`` allocates the next-available S## and persists it."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(6)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--action",
            "draft the connector module",
            "--scope",
            "src/lib/connector.py",
        ],
    )

    assert result.exit_code == 0, result.stdout
    plan = parse_plan(plan_path)
    assert [step.canonical_id for step in plan.steps] == ["S01", "S02", "S03"]
    assert plan.steps[-1].action == "draft the connector module"


def test_step_remove_retires_id_through_cli(tmp_path, runner: CliRunner) -> None:
    """``vault plan step remove`` retires the id; round-trip preserves retirement."""
    from vaultspec_core.plan.identifiers import next_available_step
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(7)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app, ["vault", "plan", "step", "remove", str(plan_path), "S04"]
    )

    assert result.exit_code == 0, result.stdout
    plan = parse_plan(plan_path)
    assert "S04" not in {step.canonical_id for step in plan.steps}
    assert "S04" in plan.retired_step_ids
    assert next_available_step(plan) == "S05"


def test_step_remove_unknown_id_emits_clean_error(tmp_path, runner: CliRunner) -> None:
    """A typed handler error renders as ``error: ...`` plus exit 1, not a traceback.

    Regression for the H-NEW-2 finding: every mutating wrapper now applies the
    ``_render_user_errors`` decorator that converts ``StepNotFoundError`` and
    its peers into user-grade CLI messages.
    """
    rng = random.Random(9)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app, ["vault", "plan", "step", "remove", str(plan_path), "S99"]
    )

    assert result.exit_code == 1
    combined = result.stdout + (result.stderr or "")
    assert "error:" in combined
    assert "S99" in combined
    assert "Traceback" not in combined


def test_tier_promote_advances_one_step(tmp_path, runner: CliRunner) -> None:
    """``vault plan tier promote`` advances the tier and synthesises a Phase wrapper."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(8)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "tier", "promote", str(plan_path)])

    assert result.exit_code == 0, result.stdout
    plan = parse_plan(plan_path)
    assert plan.frontmatter.tier.value == "L2"
    assert [phase.canonical_id for phase in plan.phases] == ["P01"]
    assert [step.canonical_id for step in plan.steps] == ["S01", "S02"]
