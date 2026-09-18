"""Behavioural guards for the population a test lane reports.

The count beside a lane's verdict is the only thing that distinguishes the run
it was supposed to be from a narrower one that passed just as green. These
assert it is read from what pytest actually wrote, and that the cases where
there is nothing to read stay visible rather than reading as zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev import testing

pytestmark = pytest.mark.unit

WRAPPED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="2" skipped="3" tests="20" time="4">
    <testcase classname="t" name="quick" time="0.01"/>
    <testcase classname="t" name="slow_one" time="7.50"/>
  </testsuite>
</testsuites>
"""

BARE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" errors="0" failures="0" skipped="0" tests="5" time="1">
  <testcase classname="t" name="quick" time="0.02"/>
</testsuite>
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_counts_are_read_from_the_record(tmp_path: Path) -> None:
    """Every outcome pytest recorded is carried through, not just the total."""
    counts = testing.read(_write(tmp_path, "wrapped.xml", WRAPPED))

    assert counts is not None
    assert counts.tests == 20
    assert counts.failures == 2
    assert counts.errors == 1
    assert counts.skipped == 3


def test_skips_are_excluded_from_what_ran(tmp_path: Path) -> None:
    """A skipped test proved nothing, so it is not counted as having run.

    This is the number a wholesale-skipping lane cannot hide behind: it exits
    0 and passes every gate, and only the population says it did no work.
    """
    counts = testing.read(_write(tmp_path, "wrapped.xml", WRAPPED))

    assert counts is not None
    assert counts.ran == 17
    assert "17 ran" in testing.describe(counts)
    assert "3 skipped" in testing.describe(counts)


def test_a_bare_testsuite_is_read_the_same_way(tmp_path: Path) -> None:
    """Both JUnit shapes are read, rather than one being assumed."""
    counts = testing.read(_write(tmp_path, "bare.xml", BARE))

    assert counts is not None
    assert counts.ran == 5


def test_a_slow_test_is_named(tmp_path: Path) -> None:
    """The outlier is reported, which is why no standing reporter is needed."""
    counts = testing.read(_write(tmp_path, "wrapped.xml", WRAPPED))

    assert counts is not None
    assert counts.slowest is not None
    assert counts.slowest[0] == "slow_one"
    assert "slowest slow_one 7.5s" in testing.describe(counts)


def test_nothing_is_named_when_nothing_is_slow(tmp_path: Path) -> None:
    """A quiet run says nothing about durations at all.

    The whole reason this replaced `--durations` is that the flag prints its
    header whether or not anything crossed the floor.
    """
    counts = testing.read(_write(tmp_path, "bare.xml", BARE))

    assert counts is not None
    assert counts.slowest is None
    assert "slowest" not in testing.describe(counts)


def test_a_missing_record_is_reported_rather_than_read_as_zero(
    tmp_path: Path,
) -> None:
    """A lane that wrote no record ran an unknown number of tests.

    Rendering that as `0 ran` would state a measurement nobody took, which is
    the display form of the mistake `EXIT-CODES.md` exists to prevent.
    """
    assert testing.read(tmp_path / "absent.xml") is None
    assert testing.describe(None) == "no record"


def test_an_unparseable_record_is_treated_as_no_record(tmp_path: Path) -> None:
    """A truncated record is missing evidence, not evidence of nothing."""
    assert testing.read(_write(tmp_path, "broken.xml", "<testsuite")) is None


def test_a_lane_is_named_by_its_record() -> None:
    """The row label comes from the lane's declaration, not from its arguments.

    Two lanes of one target select disjoint populations from identical paths;
    derived labels would render both as the same row.
    """
    argv = (
        "uv",
        "run",
        "pytest",
        "src",
        "--junit-xml=.pytest-tmp/junit-unit-serial.xml",
    )

    assert testing.lane_name(argv) == "unit-serial"


def test_each_lane_uses_a_capability_neutral_disjoint_basetemp() -> None:
    """Two lanes never share a scratch root, so neither clears the other's."""
    from dev.toolchain import lane

    parallel = testing.declared_basetemp(lane("unit-parallel", "src", "-q").argv)
    serial = testing.declared_basetemp(lane("unit-serial", "src", "-q").argv)

    assert parallel is not None
    assert serial is not None
    assert parallel != serial


def test_a_lane_scratch_root_stands_outside_the_checkout() -> None:
    """A scratch tree inside the checkout inherits the checkout's repository.

    Git discovery walks upwards, so a workspace built under the working tree
    reports this repository as its own. Every case asserting that a directory
    has no repository above it then fails on the harness rather than on the
    behaviour it was written to pin.
    """
    from dev.toolchain import lane

    basetemp = testing.declared_basetemp(lane("unit-parallel", "src", "-q").argv)

    assert basetemp is not None
    assert not basetemp.is_relative_to(Path.cwd().resolve())


def test_two_checkouts_running_one_lane_do_not_share_a_scratch_root() -> None:
    """Moving the root out of the tree must not merge concurrent checkouts.

    A runner and a developer on one host run the same lane names at the same
    time; the tree used to keep them apart for free.
    """
    left = testing.basetemp_path("unit-parallel", Path.cwd())
    right = testing.basetemp_path("unit-parallel", Path.cwd().parent)

    assert left != right


def test_a_step_that_is_not_a_lane_declares_nothing() -> None:
    """Only a test lane reports a population; nothing else is guessed at."""
    argv = ("uv", "run", "ruff", "check", "src")

    assert testing.lane_name(argv) is None
    assert testing.declared_report(argv) is None
