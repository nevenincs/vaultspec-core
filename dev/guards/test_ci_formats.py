"""The machine-readable output switch is additive and off by default.

Every gate reports console text, which CI cannot act on beyond an exit code.
These tests pin that turning annotations on changes nothing outside a workflow
run, and never overrides a format the caller chose.
"""

from __future__ import annotations

from dev import ci_formats

ON = {ci_formats.ANNOTATIONS_ENV: "true"}
RUFF_CHECK = ("uv", "run", "--no-sync", "ruff", "check", "src")
RUFF_FORMAT = ("uv", "run", "--no-sync", "ruff", "format", "--check", "src")
TY = ("uv", "run", "--no-sync", "python", "-m", "ty", "check", "src")
BASEDPYRIGHT = ("uv", "run", "--no-sync", "basedpyright")


def test_unset_changes_nothing() -> None:
    """The default - every local run - must be byte-identical to today."""
    for argv in (RUFF_CHECK, RUFF_FORMAT, TY, BASEDPYRIGHT):
        assert ci_formats.augment(argv, {}) == list(argv)


def test_ruff_check_annotates_the_diff() -> None:
    assert ci_formats.augment(RUFF_CHECK, ON)[-1] == "--output-format=github"


def test_ruff_format_is_left_alone() -> None:
    """`ruff format --check` reports a file list; it has no annotation format."""
    assert ci_formats.augment(RUFF_FORMAT, ON) == list(RUFF_FORMAT)


def test_type_checkers_emit_machine_readable_findings() -> None:
    assert ci_formats.augment(TY, ON)[-1] == "--output-format=github"
    assert ci_formats.augment(BASEDPYRIGHT, ON)[-1] == "--outputjson"


def test_a_chosen_format_is_never_overridden() -> None:
    chosen = (*RUFF_CHECK, "--output-format=json")
    assert ci_formats.augment(chosen, ON) == list(chosen)
