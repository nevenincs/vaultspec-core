"""The population a test lane actually ran, read from the lane itself.

A test lane's exit code answers one question - did anything fail - and stops
there. It cannot answer the question that goes wrong quietly: *how many tests
were there*. A marker expression narrowed by a typo, a renamed directory a path
no longer reaches, a cohort whose fixtures all skip on this host - each of those
runs, passes, exits 0, and reads exactly like the full suite.

``dev/EXIT-CODES.md`` already draws this line at zero: a lane that collected
nothing exits ``NOTHING_SELECTED`` rather than ``OK``, because a run that proved
nothing must not read as a run that proved everything. That rule is right and
incomplete - it catches the empty lane and misses the one that collected three
tests where it used to collect four thousand. Nothing in an exit code can carry
that, so the count has to travel beside it.

pytest's own JUnit XML is the record, chosen over parsing the terminal summary
or adding a reporting plugin. It is built in, so it costs no dependency; it is
written by the controller rather than the workers, so it survives ``xdist``,
which the summary line's placement in a scrolled log does not; and it carries
the counts as attributes rather than as prose, so reading it cannot drift with
a change to pytest's phrasing.
"""

from __future__ import annotations

import hashlib
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Where a lane's record is written. Under `.pytest-tmp/`, which pytest already
#: owns for its debug log and `.gitignore` already covers, so a test run cannot
#: leave an artefact in the tree it is testing.
REPORT_DIR = Path(".pytest-tmp")

#: The flag that both requests the record and says where it is. Carrying the
#: path in the command itself means the harness reads exactly what this run
#: wrote - there is no second place for the two to disagree.
REPORT_FLAG = "--junit-xml"

#: The flag that places pytest's scratch trees.
BASETEMP_FLAG = "--basetemp"

#: Where those scratch trees go. Deliberately NOT under `REPORT_DIR`: a record
#: is an artefact to keep, but a scratch tree is a *workspace under test*, and
#: one placed inside the checkout inherits this repository's `.git`. Discovery
#: walks upwards, so every case that builds a directory and asserts no
#: repository stands above it finds this one and disagrees. The system temp
#: root is the nearest place that is writable on each runner and outside any
#: checkout. The lane's directory sits DIRECTLY under it, in one flat name
#: rather than a nested pair, because pytest creates the root it is given with
#: a plain `mkdir` and fails on a missing intermediate.
BASETEMP_ROOT = Path(tempfile.gettempdir())


def report_path(lane: str) -> Path:
    """Return the record path for a named lane."""
    return REPORT_DIR / f"junit-{lane}.xml"


def basetemp_path(lane: str, workspace: Path | None = None) -> Path:
    """Return the scratch root for a named lane.

    Two lanes must never share a root, or the one that finishes first clears
    the other's fixtures mid-run. Two CHECKOUTS must not share one either: a
    runner and a developer on the same host can run the same lane name at the
    same time, and moving the root out of the tree gave up the isolation the
    tree used to supply for free. The checkout's path buys it back.

    Args:
        lane: The lane's name, unique per step.
        workspace: The checkout the lane runs in. Defaults to the working
            directory, which the harness invokes every lane from.

    Returns:
        The scratch root, outside any checkout and unique to this pair.
    """
    root = (workspace or Path.cwd()).resolve()
    token = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return BASETEMP_ROOT / f"vaultspec-pytest-{token}-{lane}"


def declared_report(argv: Sequence[str]) -> Path | None:
    """Return the record a command asked pytest to write, if it asked for one.

    Args:
        argv: The command that ran.

    Returns:
        The path, or ``None`` for any step that is not a reporting test lane.
    """
    prefix = f"{REPORT_FLAG}="
    return next(
        (Path(arg[len(prefix) :]) for arg in argv if arg.startswith(prefix)), None
    )


def declared_basetemp(argv: Sequence[str]) -> Path | None:
    """Return the scratch root a command gave pytest, if it gave one.

    Args:
        argv: The command that ran.

    Returns:
        The path, or ``None`` for any step that is not a test lane.
    """
    prefix = f"{BASETEMP_FLAG}="
    return next(
        (Path(arg[len(prefix) :]) for arg in argv if arg.startswith(prefix)), None
    )


def lane_name(argv: Sequence[str]) -> str | None:
    """Return the lane a command declared itself to be, if it declared one.

    A lane already has a name - the one `toolchain.lane` gave its record - so
    its row is labelled with that rather than with a guess derived from its
    arguments. Two lanes of one target select disjoint populations from the
    same paths and differ only in a marker expression, which a derived label
    renders as two rows saying `pytest src`.

    Args:
        argv: The command that ran.

    Returns:
        The lane name, or ``None`` for a step that is not a test lane.
    """
    report = declared_report(argv)
    return report.stem.removeprefix("junit-") if report is not None else None


#: A test slower than this is named in its lane's row. pytest's own
#: `--durations` cannot do this job: it prints its header whether or not
#: anything crossed the floor, so as a standing flag it reports "nothing to
#: report" on every lane of every run. The same record that carries the counts
#: carries each test's time, so the harness reports the outlier itself and says
#: nothing at all when there is not one.
SLOW_TEST_SECONDS = 1.0


@dataclass(frozen=True)
class Counts:
    """How many tests a lane ran, how they came out, and its slowest."""

    tests: int
    failures: int
    errors: int
    skipped: int
    slowest: tuple[str, float] | None = None

    @property
    def ran(self) -> int:
        """Tests that actually executed, rather than being skipped past."""
        return self.tests - self.skipped


def _slowest(suite: ET.Element) -> tuple[str, float] | None:
    """Return the slowest test and its time, when one crosses the floor."""
    worst_name, worst_time = "", 0.0
    for case in suite.iter("testcase"):
        try:
            seconds = float(case.attrib.get("time", 0))
        except ValueError:
            continue
        if seconds > worst_time:
            worst_name, worst_time = case.attrib.get("name", "?"), seconds
    if worst_time < SLOW_TEST_SECONDS:
        return None
    return worst_name, worst_time


def read(path: Path) -> Counts | None:
    """Read a lane's counts from its record.

    Args:
        path: The record pytest was asked to write.

    Returns:
        The counts, or ``None`` when there is no readable record - which is a
        fact worth reporting rather than one to paper over with zeroes. A lane
        that died before writing its record ran an unknown number of tests, and
        showing that as ``0 tests`` would state something nobody measured.
    """
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    # pytest writes a `testsuites` wrapper around one `testsuite`; older
    # versions and other producers write the `testsuite` alone. Totals live on
    # whichever element is present, so both shapes are read rather than assumed.
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return None

    def count(name: str) -> int:
        try:
            return int(suite.attrib.get(name, 0))
        except ValueError:
            return 0

    return Counts(
        count("tests"),
        count("failures"),
        count("errors"),
        count("skipped"),
        _slowest(suite),
    )


def describe(counts: Counts | None) -> str:
    """Render a lane's population for its verdict row.

    Skips are named whenever there are any, and never folded into the total.
    A lane whose cohort skipped wholesale exits 0 and passes every gate; the
    only thing that distinguishes it from the run it was supposed to be is this
    number, so it does not get to hide inside one.

    Args:
        counts: What the record held, or ``None`` when there was none.

    Returns:
        A short phrase, or an explicit statement that nothing was recorded.
    """
    if counts is None:
        return "no record"
    parts = [f"{counts.ran} ran"]
    if counts.skipped:
        parts.append(f"{counts.skipped} skipped")
    if counts.failures:
        parts.append(f"{counts.failures} failed")
    if counts.errors:
        parts.append(f"{counts.errors} errored")
    if counts.slowest is not None:
        name, seconds = counts.slowest
        parts.append(f"slowest {name} {seconds:.1f}s")
    return ", ".join(parts)
