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


def test_check_text_output_surfaces_fix_hint(tmp_path, runner: CliRunner) -> None:
    """`vault plan check` text output must surface a finding's fix hint,
    labelled autofix/manual - it used to be reachable only via --json."""
    body = (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#hintdemo'\n"
        "date: '2026-05-05'\n"
        "related:\n"
        "  - '[[2026-05-05-demo-adr]]'\n"
        "---\n"
        "\n"
        "# `hintdemo` plan\n"
        "\n"
        "Demo.\n"
        "\n"
        "- [ ] `S01` - first action; `src/a.py`.\n"
    )
    plan_path = tmp_path / "hint-plan.md"
    plan_path.write_text(body, encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "check", str(plan_path)])

    # Missing `tier:` -> PLAN001, which is autofixable and carries a hint.
    assert "PLAN001" in result.output
    assert "fix (autofix):" in result.output


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


def test_query_json_emits_parseable_payload(tmp_path, runner: CliRunner) -> None:
    """``vault plan query --json`` is machine-readable, matching the
    ``--json`` coverage its sibling ``vault plan status`` already has."""
    import json

    rng = random.Random(4)
    spec = make_clean_plan("L1", rng=rng, steps=4)
    spec.steps[0].checked = True
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app, ["vault", "plan", "query", str(plan_path), "--open", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["matched"] == 3
    assert payload["total"] == 4
    assert len(payload["steps"]) == 3
    assert all(s["checked"] is False for s in payload["steps"])


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


def test_tier_promote_rejects_missing_phase_flags(tmp_path, runner: CliRunner) -> None:
    """L1 -> L2 promotion without --phase-title / --phase-intent must refuse.

    The CLI does not silently substitute ``TODO: Phase title`` placeholders
    into the plan document; it requires explicit values up front.
    """
    rng = random.Random(8)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(app, ["vault", "plan", "tier", "promote", str(plan_path)])

    assert result.exit_code == 1
    assert "--phase-title" in result.stdout
    assert "--phase-intent" in result.stdout
    # Plan body must be untouched after a refused promotion.
    assert "TODO: Phase title" not in plan_path.read_text(encoding="utf-8")


def test_tier_promote_advances_one_step(tmp_path, runner: CliRunner) -> None:
    """``vault plan tier promote`` advances the tier and synthesises a Phase wrapper."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(8)
    spec = make_clean_plan("L1", rng=rng, steps=2)
    plan_path = tmp_path / "test-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "tier",
            "promote",
            str(plan_path),
            "--phase-title",
            "Implementation",
            "--phase-intent",
            "Deliver the substantive implementation work.",
        ],
    )

    assert result.exit_code == 0, result.stdout
    plan = parse_plan(plan_path)
    assert plan.frontmatter.tier.value == "L2"
    assert [phase.canonical_id for phase in plan.phases] == ["P01"]
    assert [step.canonical_id for step in plan.steps] == ["S01", "S02"]


def test_cli_repairs_manually_duplicated_step_with_display_path(
    tmp_path,
    runner: CliRunner,
) -> None:
    """Manual duplicate Step ids are repairable through display-path targeting."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(10)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=2)
    degraded = spec.render().replace("`W02.P02.S03`", "`W02.P02.S01`", 1)
    plan_path = tmp_path / "degraded-duplicate-plan.md"
    plan_path.write_text(degraded, encoding="utf-8")

    check_result = runner.invoke(app, ["vault", "plan", "check", str(plan_path)])
    assert check_result.exit_code == 1
    assert "PLAN021" in check_result.stdout
    assert "Traceback" not in check_result.stdout

    ambiguous = runner.invoke(
        app,
        ["vault", "plan", "step", "remove", str(plan_path), "S01"],
    )
    assert ambiguous.exit_code == 1
    combined = ambiguous.stdout + (ambiguous.stderr or "")
    assert "ambiguous" in combined
    assert "W01.P01.S01" in combined
    assert "W02.P02.S01" in combined

    repaired = runner.invoke(
        app,
        ["vault", "plan", "step", "remove", str(plan_path), "W02.P02.S01"],
    )
    assert repaired.exit_code == 0, repaired.stdout

    add_result = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--phase",
            "P02",
            "--action",
            "restore the degraded work item",
            "--scope",
            "tests/manual-repair.md",
        ],
    )
    assert add_result.exit_code == 0, add_result.stdout

    plan = parse_plan(plan_path)
    assert [step.canonical_id for step in plan.steps].count("S01") == 1
    assert "S01" not in plan.retired_step_ids
    assert plan.steps[-1].canonical_id == "S05"
    assert plan.steps[-1].display_path == "W02.P02.S05"

    final_check = runner.invoke(app, ["vault", "plan", "check", str(plan_path)])
    assert final_check.exit_code == 0, final_check.stdout


def test_cli_stable_insertion_uses_alpha_suffixes_for_waves_and_phases(
    tmp_path,
    runner: CliRunner,
) -> None:
    """Wave and Phase insertions use lowercase alpha suffixes, never Step suffixes."""
    from vaultspec_core.plan.parser import parse_plan

    rng = random.Random(11)
    spec = make_clean_plan("L3", rng=rng, waves=2, phases=1, steps=1)
    plan_path = tmp_path / "alpha-suffix-plan.md"
    plan_path.write_text(spec.render(), encoding="utf-8")

    wave_insert = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "wave",
            "insert",
            str(plan_path),
            "--after",
            "W01",
            "--title",
            "inserted wave",
            "--intent",
            "Inserted Wave keeps surrounding numeric ids stable.",
        ],
    )
    assert wave_insert.exit_code == 0, wave_insert.stdout

    phase_insert = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "phase",
            "insert",
            str(plan_path),
            "--after",
            "P01",
            "--title",
            "inserted phase",
            "--intent",
            "Inserted Phase keeps surrounding numeric ids stable.",
        ],
    )
    assert phase_insert.exit_code == 0, phase_insert.stdout

    step_add = runner.invoke(
        app,
        [
            "vault",
            "plan",
            "step",
            "add",
            str(plan_path),
            "--phase",
            "P01a",
            "--action",
            "exercise the suffixed phase",
            "--scope",
            "tests/alpha-suffix.md",
        ],
    )
    assert step_add.exit_code == 0, step_add.stdout

    plan = parse_plan(plan_path)
    assert [wave.canonical_id for wave in plan.waves] == ["W01", "W01a", "W02"]
    assert [phase.canonical_id for phase in plan.waves[0].phases] == [
        "P01",
        "P01a",
    ]
    assert any(step.display_path == "W01.P01a.S03" for step in plan.steps)
    assert not any(step.canonical_id.endswith("a") for step in plan.steps)

    check_result = runner.invoke(app, ["vault", "plan", "check", str(plan_path)])
    assert check_result.exit_code == 0, check_result.stdout
    assert "PLAN023" in check_result.stdout

    phase_remove = runner.invoke(
        app,
        ["vault", "plan", "phase", "remove", str(plan_path), "P01a"],
    )
    assert phase_remove.exit_code == 0, phase_remove.stdout

    wave_remove = runner.invoke(
        app,
        ["vault", "plan", "wave", "remove", str(plan_path), "W01a"],
    )
    assert wave_remove.exit_code == 0, wave_remove.stdout

    reparsed = parse_plan(plan_path)
    assert "P01a" in reparsed.retired_phase_ids
    assert "W01a" in reparsed.retired_wave_ids
    assert "S03" in reparsed.retired_step_ids
