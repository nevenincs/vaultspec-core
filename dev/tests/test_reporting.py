"""Behavioural guards for what a harness run tells its reader.

The verdict a step prints is as much a contract as the status it exits with,
and it is the half a human actually reads. These assert the two properties
that make it trustworthy: that every status the contract names is DISTINGUISHED
in the output rather than collapsed onto pass/fail, and that a step's label
identifies which tool ran even when a target runs the same tool twice.
"""

from __future__ import annotations

import pytest

from dev import reporting
from dev.exit_codes import (
    DRIFT,
    FAILED,
    NOTHING_SELECTED,
    OK,
    TOOL_BROKEN,
    TOOL_MISSING,
)

pytestmark = pytest.mark.unit


def test_every_contract_status_has_its_own_word() -> None:
    """No two statuses share a word, and none is missing one.

    Collapsing them is the defect this module exists to prevent: `EMPTY` and
    `BROKEN` both used to reach the terminal as silence, which reads exactly
    like the clean pass neither of them is.
    """
    codes = [OK, FAILED, DRIFT, TOOL_BROKEN, NOTHING_SELECTED, TOOL_MISSING]
    words = [reporting.status_word(code) for code in codes]

    assert len(set(words)) == len(words), f"statuses share a word: {words}"
    assert all(word.strip() for word in words)


def test_an_unnamed_status_shows_its_number() -> None:
    """A status the contract has no word for is shown, not flattened.

    Reading it as `FAILED` would hide the one fact worth chasing: that a tool
    exited with something nobody has accounted for.
    """
    assert reporting.status_word(42) == "EXIT 42"


def test_the_status_column_aligns_whatever_the_word() -> None:
    """Rows line up, so a column of verdicts can be read down rather than across."""
    lines = [reporting.row("tool", code, 1.0) for code in (OK, FAILED, TOOL_MISSING)]
    offsets = [line.index("1.0s") for line in lines]

    assert len(set(offsets)) == 1, f"duration column is ragged: {lines}"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("uv", "run", "--no-sync", "ruff", "check", "src", "dev"), "ruff check"),
        (("uv", "run", "--no-sync", "ruff", "format", "--check", "src"), "ruff format"),
        (("uv", "run", "--no-sync", "python", "-m", "ty", "check", "src"), "ty check"),
        (
            ("uv", "run", "--no-sync", "python", "-m", "dev.actionlint"),
            "dev.actionlint",
        ),
        (
            ("uv", "run", "--no-sync", "complexipy", "src/vaultspec_core", "--failed"),
            "complexipy --failed",
        ),
        (
            ("uv", "run", "--no-sync", "mdformat", "--check", "README.md"),
            "mdformat --check",
        ),
        (("taplo", "lint", "*.toml"), "taplo lint"),
        (("uv", "lock", "--check"), "uv lock"),
    ],
)
def test_a_label_names_the_tool_not_its_arguments(
    argv: tuple[str, ...], expected: str
) -> None:
    """The label answers "which tool", which is what a reader acts on.

    Paths, globs and bare numbers are arguments: they say what the tool was
    pointed at, never which tool it was.
    """
    assert reporting.tool_label(argv) == expected


def test_colliding_labels_are_told_apart_by_what_differs() -> None:
    """Two steps of one target never report under the same name.

    Identical rows would say that three things ran without saying which - the
    same loss of signal as saying nothing, arrived at by repetition.
    """
    commands = [
        ("uv", "run", "--no-sync", "python", "-m", "ty", "check", "--platform", plat)
        for plat in ("linux", "darwin", "win32")
    ]

    labels = reporting.distinct_labels(commands)

    assert len(set(labels)) == 3, f"labels collided: {labels}"
    assert all(label.startswith("ty check") for label in labels)
    assert {"linux", "darwin", "win32"} == {
        label.rsplit(" ", 1)[-1] for label in labels
    }


def test_labels_that_do_not_collide_are_left_alone() -> None:
    """Disambiguation costs a word, so it is spent only where it buys one."""
    commands = [
        ("uv", "run", "--no-sync", "ruff", "check", "src"),
        ("uv", "run", "--no-sync", "ruff", "format", "--check", "src"),
    ]

    assert reporting.distinct_labels(commands) == ["ruff check", "ruff format"]


def test_the_verdict_counts_each_status_separately() -> None:
    """An aggregate's closing line distinguishes what went wrong, not just that.

    Two failures and two unrunnable tools are different situations with
    different remedies; a single "4 failed" would merge them.
    """
    line = reporting.verdict("lint all", [OK, FAILED, TOOL_MISSING, OK], 12.0)

    assert "2 ok" in line
    assert f"1 {reporting.status_word(FAILED)}" in line
    assert f"1 {reporting.status_word(TOOL_MISSING)}" in line


def test_the_verdict_of_a_clean_run_says_so() -> None:
    """A clean aggregate still reports, rather than trailing off into silence."""
    assert "11 ok" in reporting.verdict("lint all", [OK] * 11, 74.5)


def test_verbose_is_off_unless_the_environment_asks() -> None:
    """The escape hatch is opt-in, and blank does not mean set."""
    assert not reporting.verbose({})
    assert not reporting.verbose({reporting.VERBOSE_ENV: "  "})
    assert reporting.verbose({reporting.VERBOSE_ENV: "1"})
