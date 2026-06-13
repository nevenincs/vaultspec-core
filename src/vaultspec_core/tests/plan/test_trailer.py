"""Tests for the commit-linkage trailer module and its CLI verbs (issue #159).

Covers the pure parse/format/validate helpers in
:mod:`vaultspec_core.plan.trailer` and the ``vault plan trailer emit`` /
``validate`` verbs, including the load-bearing constraint that ``validate``
always exits zero (the trailer is enrichment, never a prerequisite).
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.plan.trailer import (
    FEATURE_TRAILER_KEY,
    STEP_TRAILER_KEY,
    format_feature_trailer,
    format_step_trailer,
    parse_message,
    validate_message,
    validate_value,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(env={"NO_COLOR": "1"})


# ---- value validation -------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["S06", "S117", "P02.S06", "W01.P02.S06", "W01.P02a.S06", "P02", "W01.P02", "P02a"],
)
def test_step_trailer_accepts_valid_display_paths(value: str) -> None:
    """Every L1..L4 Step and Phase display path validates for the Step key."""
    assert validate_value(STEP_TRAILER_KEY, value) is None


@pytest.mark.parametrize(
    "value",
    ["S6", "s06", "P2.S06", "S06a", "W1.P02.S06", "X01.S06", "P02.S06.", "", "W01"],
)
def test_step_trailer_rejects_malformed(value: str) -> None:
    """Malformed Step values report a reason rather than validating."""
    assert validate_value(STEP_TRAILER_KEY, value) is not None


@pytest.mark.parametrize(
    "value", ["auth-refactor", "#auth-refactor", "graph", "a", "x9-y-z", "#graph"]
)
def test_feature_trailer_accepts_valid_tags(value: str) -> None:
    assert validate_value(FEATURE_TRAILER_KEY, value) is None


@pytest.mark.parametrize(
    "value", ["Auth", "-leading", "with space", "UPPER", "", "##double"]
)
def test_feature_trailer_rejects_malformed(value: str) -> None:
    assert validate_value(FEATURE_TRAILER_KEY, value) is not None


def test_validate_value_unknown_key_returns_reason() -> None:
    assert validate_value("Vaultspec-Bogus", "S01") is not None


# ---- parsing ----------------------------------------------------------------


def test_parse_message_finds_both_keys_case_insensitively() -> None:
    message = (
        "feat: do the thing\n\n"
        "Body paragraph explaining why.\n\n"
        "Vaultspec-Step: W01.P02.S06\n"
        "vaultspec-feature: auth-refactor\n"
        "Co-authored-by: Someone <x@y.z>\n"
    )
    trailers = parse_message(message)
    assert [(t.key, t.value) for t in trailers] == [
        (STEP_TRAILER_KEY, "W01.P02.S06"),
        (FEATURE_TRAILER_KEY, "auth-refactor"),
    ]
    # Line numbers are 1-based and point at the trailer lines.
    assert trailers[0].line_number == 5
    assert trailers[1].line_number == 6


def test_parse_message_without_trailers_is_empty() -> None:
    assert parse_message("just a subject line\n\nand a body") == []


# ---- validate_message -------------------------------------------------------


def test_validate_message_clean_returns_no_problems() -> None:
    message = "feat: x\n\nVaultspec-Step: P02.S06\nVaultspec-Feature: graph\n"
    assert validate_message(message) == []


def test_validate_message_flags_malformed_value() -> None:
    message = "feat: x\n\nVaultspec-Step: not-a-path\n"
    problems = validate_message(message)
    assert len(problems) == 1
    assert problems[0].key == STEP_TRAILER_KEY
    assert problems[0].value == "not-a-path"
    assert problems[0].line_number == 3


def test_validate_message_trailerless_is_clean() -> None:
    assert validate_message("chore: tidy up\n") == []


# ---- formatting -------------------------------------------------------------


def test_format_step_trailer_roundtrips() -> None:
    line = format_step_trailer("W01.P02.S06")
    assert line == "Vaultspec-Step: W01.P02.S06"
    assert validate_message(line) == []


def test_format_feature_trailer_strips_leading_hash() -> None:
    assert (
        format_feature_trailer("#auth-refactor") == "Vaultspec-Feature: auth-refactor"
    )
    assert format_feature_trailer("graph") == "Vaultspec-Feature: graph"


def test_format_step_trailer_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invalid"):
        format_step_trailer("S6")


def test_format_feature_trailer_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invalid"):
        format_feature_trailer("Bad Tag")


# ---- CLI: emit --------------------------------------------------------------


def test_cli_emit_step(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["vault", "plan", "trailer", "emit", "--step", "W01.P02.S06"]
    )
    assert result.exit_code == 0, result.output
    assert "Vaultspec-Step: W01.P02.S06" in result.output


def test_cli_emit_feature(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["vault", "plan", "trailer", "emit", "--feature", "#auth-refactor"]
    )
    assert result.exit_code == 0, result.output
    assert "Vaultspec-Feature: auth-refactor" in result.output


def test_cli_emit_requires_exactly_one(runner: CliRunner) -> None:
    both = runner.invoke(
        app,
        ["vault", "plan", "trailer", "emit", "--step", "S01", "--feature", "x"],
    )
    assert both.exit_code == 1
    assert "exactly one" in both.output

    neither = runner.invoke(app, ["vault", "plan", "trailer", "emit"])
    assert neither.exit_code == 1
    assert "exactly one" in neither.output


def test_cli_emit_invalid_step_is_usage_error(runner: CliRunner) -> None:
    result = runner.invoke(app, ["vault", "plan", "trailer", "emit", "--step", "S6"])
    assert result.exit_code == 1
    assert "invalid" in result.output


# ---- CLI: validate (always exits zero) --------------------------------------


def test_cli_validate_clean_exits_zero(runner: CliRunner, tmp_path) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: x\n\nVaultspec-Step: P02.S06\n", encoding="utf-8")
    result = runner.invoke(app, ["vault", "plan", "trailer", "validate", str(msg)])
    assert result.exit_code == 0, result.output


def test_cli_validate_malformed_reports_but_exits_zero(
    runner: CliRunner, tmp_path
) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: x\n\nVaultspec-Step: garbage\n", encoding="utf-8")
    result = runner.invoke(app, ["vault", "plan", "trailer", "validate", str(msg)])
    assert result.exit_code == 0, result.output
    assert "advisory" in result.output
    assert "garbage" in result.output


def test_cli_validate_trailerless_exits_zero(runner: CliRunner, tmp_path) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("chore: no trailers here\n", encoding="utf-8")
    result = runner.invoke(app, ["vault", "plan", "trailer", "validate", str(msg)])
    assert result.exit_code == 0, result.output


def test_cli_validate_missing_file_exits_zero(runner: CliRunner, tmp_path) -> None:
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["vault", "plan", "trailer", "validate", str(missing)])
    assert result.exit_code == 0, result.output


def test_cli_validate_json_envelope(runner: CliRunner, tmp_path) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: x\n\nVaultspec-Feature: Bad Tag\n", encoding="utf-8")
    result = runner.invoke(
        app, ["vault", "plan", "trailer", "validate", str(msg), "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema"] == "vaultspec.vault.plan.trailer.validate.v1"
    assert len(payload["data"]["problems"]) == 1
    assert payload["data"]["problems"][0]["key"] == FEATURE_TRAILER_KEY
