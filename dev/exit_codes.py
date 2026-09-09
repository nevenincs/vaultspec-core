"""The repository-wide exit-code contract.

A command's exit code is its contract with CI and with the developer. This
module states that contract once, as data, so every repository in the fleet
means the same thing by the same number. It is stdlib-only and imports nothing
from the rest of ``dev`` so that any instrument - including one that runs
before the virtual environment exists - can depend on it.

The governing distinction is between a tool that RAN and reported findings and
a tool that FAILED TO RUN. Advisory targets suppress the first and must never
suppress the second: a scanner that crashed, was misconfigured, or was never
installed reports nothing, and "reported nothing" is not "found nothing".

Verb classes, keyed to CONSEQUENCE:

``check``
    GATES. Read-only. A finding is a verdict and fails the build.
``fix``
    MUTATES. Exits :data:`OK` on success whether or not it changed anything.
    Under :data:`FIX_STRICT_ENV` (set by CI) a fix that HAD to change
    something exits :data:`DRIFT`, because in CI a repairable defect is an
    uncommitted repair.
``test``
    GATES. Additionally, a lane that ran nothing exits
    :data:`NOTHING_SELECTED` - never :data:`OK`.
``audit``
    ADVISORY, except the DEPENDENCY audit, which GATES. A published advisory
    against a pinned version is a verdict; every other scan yields a lead.
``build``
    GATES.
``health``
    Measures. Always exits :data:`OK`; its output is the product.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Container

#: Success. The command ran and found nothing that gates.
OK = 0

#: Generic failure: the command ran and reported a gating result.
FAILED = 1

#: `just init`: a required HOST tool is absent (L6). Reserved fleet-wide so
#: nothing else claims it. Outside `init`, an absent executable discovered at
#: dispatch time is :data:`TOOL_MISSING`, which carries the shell's own
#: command-not-found meaning and needs no lookup table.
INIT_HOST_TOOL_MISSING = 2

#: `just init`: the environment exists but is stale relative to its inputs.
INIT_STALE = 3

#: `just init`: one bootstrap step failed.
INIT_STEP_FAILED = 4

#: Managed content drifted from its generated form. Emitted by `fix` under
#: :data:`FIX_STRICT_ENV`, and by `init` when the lockfile and environment
#: disagree (L6).
DRIFT = 5

#: `just init`: the environment is held open by another process (L6).
INIT_LOCKED = 6

#: A tool failed to RUN: it crashed, was misconfigured, or exited with a status
#: outside :data:`FINDINGS_CODES` and :data:`OK`. Distinct from
#: :data:`TOOL_MISSING`, which is the narrower "the executable is not there";
#: this covers a tool that started and could not do its job.
#:
#: It is one code for gates and advisories alike ON PURPOSE. "The scanner did
#: not run" means the same thing to a reader whichever kind of target hit it,
#: and the difference that matters - whether the run gates - is already carried
#: by the target's declaration, not by a second number.
TOOL_BROKEN = 7

#: The advisory-facing name for :data:`TOOL_BROKEN`. Advisory means "these
#: findings do not gate", not "this scanner's silence is trustworthy": the
#: findings are suppressed, a tool that could not run is not.
ADVISORY_BROKEN = TOOL_BROKEN

#: Nothing ran. An empty selection, a suite in which every test skipped, or an
#: aggregate with no reachable steps. Deliberately non-zero: a run that proved
#: nothing must not be readable as a run that proved everything.
NOTHING_SELECTED = 8

#: A required tool is not installed and has no fallback. 127 is the
#: conventional shell status for command-not-found, which keeps the meaning
#: legible in CI logs and to anyone reading the number directly.
TOOL_MISSING = 127

#: Statuses meaning "the tool ran and reported findings". Every scanner in the
#: fleet - ruff, bandit, vulture, deptry, jscpd, complexipy, npm audit,
#: cargo deny - uses 1 for this. An advisory target suppresses exactly these;
#: anything else is :data:`ADVISORY_BROKEN`.
FINDINGS_CODES = frozenset({FAILED})

#: pytest's status for "no tests were collected", mapped onto
#: :data:`NOTHING_SELECTED` so an empty lane cannot read as a pass.
PYTEST_NO_TESTS_COLLECTED = 5

#: Set by CI. Makes `fix` report :data:`DRIFT` when it had to change something.
FIX_STRICT_ENV = "VAULTSPEC_FIX_STRICT"

#: Set by a lane that is legitimately allowed to collect nothing.
ALLOW_EMPTY_ENV = "VAULTSPEC_ALLOW_EMPTY_SELECTION"


def advisory_result(code: int, findings: Container[int] = FINDINGS_CODES) -> int:
    """Collapse an advisory step's status onto the contract.

    Args:
        code: The status the advisory tool exited with.
        findings: The statuses THIS tool uses to mean "I found something".
            Defaults to :data:`FINDINGS_CODES`, which is right for every
            scanner in the fleet but one: vulture reports dead code with 3 and
            reserves 1 and 2 for invalid input and invalid arguments. Reading
            its 3 as breakage would silence the finding; reading its 1 as a
            finding would silence a broken invocation. A tool that does not use
            1 must therefore SAY so, which is the difference between this and a
            blanket flag.

    Returns:
        :data:`OK` when the tool ran and merely reported findings, otherwise
        :data:`ADVISORY_BROKEN`. This is the whole of the mechanism that
        `; exit 0` got wrong: `exit 0` maps EVERY status onto success, so a
        scanner that was missing or crashed reported exactly like a clean run.
    """
    if code == OK or code in findings:
        return OK
    return ADVISORY_BROKEN


def selection_result(code: int) -> int:
    """Map a test runner's "nothing collected" status onto the contract.

    Args:
        code: The status the test runner exited with.

    Returns:
        :data:`NOTHING_SELECTED` when nothing ran, otherwise ``code``.
    """
    if code == PYTEST_NO_TESTS_COLLECTED:
        return NOTHING_SELECTED
    return code
