"""The repository-wide exit-code contract, enforced.

`dev/EXIT-CODES.md` states the contract in prose and `dev/exit_codes.py` states
it as data. This module is what makes either of them true tomorrow.

Two populations are asserted:

1. The mapping functions behave as written - in particular that an advisory
   target suppresses FINDINGS and never suppresses a tool that failed to RUN.
2. No justfile recipe re-implements a swallow by hand. `; exit 0`, a trailing
   bare `exit 0`, and `|| true` all map every non-zero status onto success,
   which is the defect the structural `advisory=True` mechanism exists to
   replace. A `$LASTEXITCODE` test on a standalone recipe line is also
   rejected: `just` runs each such line as its own shell process, so the
   variable is unset and the guard is dead code that reads as load-bearing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dev.exit_codes import (
    ADVISORY_BROKEN,
    ALLOW_EMPTY_ENV,
    DRIFT,
    FAILED,
    FINDINGS_CODES,
    FIX_STRICT_ENV,
    INIT_HOST_TOOL_MISSING,
    INIT_LOCKED,
    INIT_STALE,
    INIT_STEP_FAILED,
    NOTHING_SELECTED,
    OK,
    PYTEST_NO_TESTS_COLLECTED,
    TOOL_MISSING,
    advisory_result,
    selection_result,
)

pytestmark = pytest.mark.repo

#: Repository root: this file is `<root>/dev/guards/<name>.py`.
ROOT = Path(__file__).resolve().parents[2]

#: A line carrying this marker is exempt, and must say why on the same line.
ALLOW = "exit-code-contract: allow"

#: Hand-rolled swallows. Each maps EVERY non-zero status onto success, so a
#: tool that crashed or was never installed reports like a clean run.
SWALLOWS = (
    (re.compile(r";\s*exit\s+0\b"), "`; exit 0` swallows a crashed or missing tool"),
    (re.compile(r"\|\|\s*true\b"), "`|| true` swallows a crashed or missing tool"),
    (re.compile(r"^\s*@?exit\s+0\s*$"), "a trailing bare `exit 0` swallows the body"),
)

#: `$LASTEXITCODE` is only meaningful inside one shell process.
LASTEXITCODE = re.compile(r"\$LASTEXITCODE")

#: A recipe line that opens a `just` recipe body (indented continuation).
BODY = re.compile(r"^[ \t]+\S")

#: A shebang recipe runs its whole body in ONE process, so state survives.
SHEBANG = re.compile(r"^[ \t]*#!")


#: Trees that hold no authored justfile and are expensive to walk.
PRUNED = frozenset({".git", ".venv", ".logs", "node_modules", "target", "__pycache__"})


def justfiles() -> list[Path]:
    """Return every authored justfile in the checkout.

    Raises:
        AssertionError: When the glob matched nothing. An empty corpus makes
            the two filesystem assertions below pass vacuously - no files, no
            offenders - which is how a guard retires itself instead of failing
            when a directory is renamed out from under it. `Path.rglob` treats
            "missing" and "empty" identically and raises for neither, so the
            expectation has to be stated. It is stated HERE, in the helper that
            derives the corpus, rather than in each caller, because a caller
            that forgot would be the hole this closes.
    """
    found = [p for p in ROOT.rglob("*.just") if not PRUNED & set(p.parts)]
    root_file = ROOT / "justfile"
    if root_file.exists():
        found.append(root_file)
    assert found, (
        f"no justfile found under {ROOT}. Every repository in this fleet has "
        "at least a root `justfile`; finding none means this guard is looking "
        "in the wrong place, not that the tree is clean."
    )
    return sorted(found)


def _body_lines(text: str) -> list[tuple[int, str, bool]]:
    """Return `(lineno, line, in_shebang_recipe)` for every recipe-body line."""
    out: list[tuple[int, str, bool]] = []
    shebang = False
    continued = False
    for number, line in enumerate(text.splitlines(), start=1):
        if not BODY.match(line):
            shebang = False
            continued = False
            continue
        if not continued and SHEBANG.match(line):
            shebang = True
        out.append((number, line, shebang or continued))
        continued = line.rstrip().endswith("\\")
    return out


# --- 1. the mapping functions -------------------------------------------------


def test_findings_are_suppressed_by_an_advisory_target() -> None:
    """A scanner that RAN and reported findings does not gate."""
    for code in FINDINGS_CODES:
        assert advisory_result(code) == OK


def test_a_clean_advisory_run_is_success() -> None:
    assert advisory_result(OK) == OK


def test_a_missing_tool_is_never_suppressed() -> None:
    """The defect `; exit 0` caused, asserted as impossible."""
    assert advisory_result(TOOL_MISSING) == ADVISORY_BROKEN


@pytest.mark.parametrize("code", [2, 3, 4, 5, 6, 9, 126, 127, 139, 255])
def test_every_non_findings_status_propagates(code: int) -> None:
    """Crash, misconfiguration, signal death: all distinguishable from clean."""
    assert code in FINDINGS_CODES or advisory_result(code) == ADVISORY_BROKEN


def test_a_declared_findings_status_is_suppressed() -> None:
    """A tool that says which status means "found something" is believed.

    vulture reports dead code with 3 and reserves 1 for invalid input. Under
    the `{1}` default its findings read as a broken scanner and its broken
    invocations read as findings - both backwards, and both silent. So a tool
    that does not use 1 declares what it does use.
    """
    vulture = frozenset({3})
    assert advisory_result(3, vulture) == OK
    assert advisory_result(0, vulture) == OK


def test_a_declared_findings_set_still_catches_breakage() -> None:
    """Declaring a findings status narrows the suppression, never widens it."""
    vulture = frozenset({3})
    assert advisory_result(1, vulture) == ADVISORY_BROKEN
    assert advisory_result(2, vulture) == ADVISORY_BROKEN
    assert advisory_result(TOOL_MISSING, vulture) == ADVISORY_BROKEN


def test_an_empty_selection_is_not_a_pass() -> None:
    assert selection_result(PYTEST_NO_TESTS_COLLECTED) == NOTHING_SELECTED
    assert NOTHING_SELECTED != OK


def test_a_real_test_result_passes_through_selection_mapping() -> None:
    assert selection_result(OK) == OK
    assert selection_result(FAILED) == FAILED


def test_the_codes_are_distinct() -> None:
    """Two meanings sharing a number is the ambiguity this contract removes."""
    codes = [
        OK,
        FAILED,
        INIT_HOST_TOOL_MISSING,
        INIT_STALE,
        INIT_STEP_FAILED,
        DRIFT,
        INIT_LOCKED,
        ADVISORY_BROKEN,
        NOTHING_SELECTED,
        TOOL_MISSING,
    ]
    assert len(codes) == len(set(codes))


def test_the_init_codes_match_the_agreed_allocation() -> None:
    """L6 allocated 2-6 for `just init`; nothing else may claim them."""
    allocated = (
        INIT_HOST_TOOL_MISSING,
        INIT_STALE,
        INIT_STEP_FAILED,
        DRIFT,
        INIT_LOCKED,
    )
    assert allocated == (2, 3, 4, 5, 6)


def test_the_environment_switches_are_named_once() -> None:
    assert FIX_STRICT_ENV == "VAULTSPEC_FIX_STRICT"
    assert ALLOW_EMPTY_ENV == "VAULTSPEC_ALLOW_EMPTY_SELECTION"


# --- 2. no hand-rolled swallows in any justfile -------------------------------


def test_no_recipe_swallows_a_failure_by_hand() -> None:
    offences: list[str] = []
    for path in justfiles():
        text = path.read_text(encoding="utf-8")
        for number, line, _ in _body_lines(text):
            if ALLOW in line:
                continue
            for pattern, why in SWALLOWS:
                if pattern.search(line):
                    rel = path.relative_to(ROOT).as_posix()
                    offences.append(f"{rel}:{number}: {why}\n    {line.strip()}")
    assert not offences, (
        "Express advisory intent structurally with `advisory=True` in the "
        "toolchain table, which suppresses findings only. See "
        "dev/EXIT-CODES.md.\n" + "\n".join(offences)
    )


def test_no_dead_lastexitcode_guard() -> None:
    """`$LASTEXITCODE` on a standalone recipe line is unset, so it is dead."""
    offences: list[str] = []
    for path in justfiles():
        text = path.read_text(encoding="utf-8")
        for number, line, joined in _body_lines(text):
            if joined or ALLOW in line:
                continue
            if LASTEXITCODE.search(line):
                rel = path.relative_to(ROOT).as_posix()
                offences.append(f"{rel}:{number}: {line.strip()}")
    assert not offences, (
        "`just` runs each standalone recipe line in its own shell process, so "
        "$LASTEXITCODE is unset and this guard never fires. Move the logic "
        "into dev/ and let the runner own the exit code. See "
        "dev/EXIT-CODES.md.\n" + "\n".join(offences)
    )


def test_the_contract_is_documented_beside_its_implementation() -> None:
    doc = ROOT / "dev" / "EXIT-CODES.md"
    assert doc.exists(), "dev/EXIT-CODES.md is the canonical statement"
    body = doc.read_text(encoding="utf-8")
    for token in ("ADVISORY_BROKEN", "NOTHING_SELECTED", "TOOL_MISSING"):
        assert token in body, f"{token} is unexplained in dev/EXIT-CODES.md"
