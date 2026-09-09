"""What a harness run PRINTS, decided in one place.

Third of a trio that between them own everything a step communicates.
:mod:`dev.exit_codes` says what a status MEANS; :mod:`dev.ci_formats` says what
a tool prints FOR MACHINES; this module says what a run prints FOR A HUMAN.

The governing rule is the display counterpart of the one in ``EXIT-CODES.md``:

    The harness owns the VERDICT. The tool owns the DIAGNOSIS.

A tool is heard when it has a diagnosis - a finding, a crash, a stack trace.
On a clean pass it has nothing to say that the harness cannot say better, and
what it says instead is narration: ``All checks passed!``, ``696 files already
formatted``, ``0 errors, 0 warnings, 0 notes``, an INFO log about locating its
own config file, and, from three of them, nothing at all. Six vocabularies for
one word, and one of them indistinguishable from a checker that never ran.

So the harness states the verdict itself, once per step, in the vocabulary of
the exit-code contract - which is the only vocabulary in which "passed",
"could not run" and "selected nothing" are three different words rather than
three silences.

Withholding output is safe in exactly one direction, and the asymmetry is the
whole design: a step that FAILED is replayed in full, preceded by the command
that produced it, so nothing a reader needs in order to act is ever suppressed.
Suppression applies to success only, and only where a target declares that its
output is narration rather than its product.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from dev.exit_codes import (
    DRIFT,
    FAILED,
    INIT_HOST_TOOL_MISSING,
    INIT_LOCKED,
    INIT_STALE,
    INIT_STEP_FAILED,
    NOTHING_SELECTED,
    OK,
    TOOL_BROKEN,
    TOOL_MISSING,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Set to any non-empty value to stream every step and echo every command, as
#: the harness did unconditionally before this module existed. The escape hatch
#: for watching a long step work rather than waiting for its verdict.
VERBOSE_ENV = "VAULTSPEC_VERBOSE"

#: The community standard for suppressing colour; honoured whatever its value.
NO_COLOR_ENV = "NO_COLOR"

#: Width the step label is padded to. Fixed rather than measured because rows
#: print as each step COMPLETES - a width derived from the whole target would
#: have to be known before the first step runs, which costs the live feedback
#: that makes a slow gate bearable to watch.
LABEL_WIDTH = 22

#: Width the status word is padded to, sized to the longest in `STATUS_WORDS`.
STATUS_WIDTH = 13

#: One word per status, from the exit-code contract. The point of naming all of
#: them is that a reader never has to look a number up to know whether the code
#: is wrong or the toolchain is: `FAILED` is a verdict about the repository,
#: `BROKEN` and `MISSING` are verdicts about the harness, and `EMPTY` is the
#: one that used to read as success.
STATUS_WORDS = {
    OK: "ok",
    FAILED: "FAILED",
    INIT_HOST_TOOL_MISSING: "NO HOST TOOL",
    INIT_STALE: "STALE",
    INIT_STEP_FAILED: "STEP FAILED",
    DRIFT: "DRIFT",
    INIT_LOCKED: "LOCKED",
    TOOL_BROKEN: "BROKEN",
    NOTHING_SELECTED: "EMPTY",
    TOOL_MISSING: "MISSING",
}

_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def verbose(env: Mapping[str, str] | None = None) -> bool:
    """Whether every step should stream and echo its command."""
    environment = os.environ if env is None else env
    return bool(environment.get(VERBOSE_ENV, "").strip())


def colouring() -> bool:
    """Whether to emit ANSI colour on the harness's own lines.

    Colour is signal here rather than decoration - one red word among green
    ones is the fastest read of an eleven-dimension aggregate - so it is on at
    a terminal and off everywhere its escapes would become literal text.
    """
    return sys.stdout.isatty() and not os.environ.get(NO_COLOR_ENV, "")


def status_word(code: int) -> str:
    """Return the contract's word for a status, or the bare number.

    Args:
        code: The status a step exited with.

    Returns:
        The contract's word, or ``EXIT <code>`` for a status the contract does
        not name. An unnamed status is shown rather than collapsed onto
        ``FAILED``, because a number the contract has no word for is a fact
        about the tool that the reader has to see to chase.
    """
    return STATUS_WORDS.get(code, f"EXIT {code}")


def _paint(text: str, code: int) -> str:
    if not colouring():
        return text
    if code == OK:
        return f"{_GREEN}{text}{_RESET}"
    if code == FAILED:
        return f"{_RED}{text}{_RESET}"
    return f"{_YELLOW}{text}{_RESET}"


def _dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}" if colouring() else text


def _is_subcommand(token: str) -> bool:
    """Whether a token reads as a subcommand rather than an argument.

    A path, a glob, a bare number and a flag all say something about the
    invocation and nothing about which tool ran, which is what a label is for.
    """
    if not token or token.startswith("-") or token.isdigit():
        return False
    return not set(token) & set("/\\.*=")


def _significant(argv: Sequence[str]) -> list[str]:
    """Strip the wrappers that prefix nearly every step and identify nothing."""
    parts = list(argv)
    if parts[:2] == ["uv", "run"]:
        parts = [part for part in parts[2:] if part != "--no-sync"]
    if not parts:
        return []
    head = os.path.basename(parts[0])
    if head.lower().endswith(".exe"):
        head = head[: -len(".exe")]
    # `python -m pkg` is named by its MODULE: `-m ty check` is `ty`, not
    # `python`, and every module-run step in the toolchain reads the same way.
    if head.startswith("python") and parts[1:2] == ["-m"] and len(parts) > 2:
        return list(parts[2:])
    return [head, *parts[1:]]


def tool_label(argv: Sequence[str]) -> str:
    """Name the tool a command runs, for use as a step's row label.

    The label answers "which tool", because that is what a reader acts on. The
    full command is not a label, it is a reproduction recipe, and it is printed
    as one when the step fails.

    Args:
        argv: The command about to run.

    Returns:
        A short name such as ``ruff check``, ``ty check`` or ``complexipy``.
    """
    parts = _significant(argv)
    # A step that runs no command - a section header - has no tool to name.
    if not parts:
        return ""
    head = parts[0]
    subcommand = next((token for token in parts[1:] if _is_subcommand(token)), "")
    if subcommand:
        return f"{head} {subcommand}"
    # No subcommand at all - a tool invoked as `mdformat --check <paths>` or
    # `complexipy <path> --failed`. Its first flag is then the only thing in
    # the command that distinguishes it from its siblings.
    flag = next((token for token in parts[1:] if token.startswith("-")), "")
    return f"{head} {flag.split('=')[0]}".strip()


def distinct_labels(commands: Sequence[Sequence[str]]) -> list[str]:
    """Label each command, keeping labels that collide told apart.

    Two steps of one target can share a tool and differ only in a flag - the
    three ``--python-platform`` passes, the wrapped and unwrapped Markdown
    checks. Identical rows for them would report that three things ran without
    saying which, so a collision is resolved by appending the first argument on
    which the colliding commands actually differ. That token is by construction
    the thing the steps were distinguished by in the first place.

    Args:
        commands: Each step's argument vector, in the order they will run.

    Returns:
        One label per command, positionally.
    """
    labels = [tool_label(command) for command in commands]
    for label in set(labels):
        group = [index for index, other in enumerate(labels) if other == label]
        if len(group) < 2:
            continue
        argvs = [_significant(commands[index]) for index in group]
        width = max(len(argv) for argv in argvs)
        for position in range(width):
            tokens = [argv[position] if position < len(argv) else "" for argv in argvs]
            if len(set(tokens)) == len(tokens):
                for index, token in zip(group, tokens, strict=True):
                    labels[index] = f"{label} {token}".strip()
                break
    return labels


def _duration(seconds: float) -> str:
    return f"{seconds:6.1f}s"


def row(label: str, code: int, seconds: float, detail: str = "") -> str:
    """Render one step's verdict line.

    Padded before colouring, never after: the escape sequences carry no width,
    so a column measured on the coloured string is off by exactly their length
    and the durations stop lining up under each other.

    Args:
        label: The step's name.
        code: The status it exited with.
        seconds: How long it took.
        detail: What the step MEASURED, where a status alone understates it -
            a test lane's population, which no exit code can carry.
    """
    word = f"{status_word(code):<{STATUS_WIDTH}}"
    line = f"  {label:<{LABEL_WIDTH}}{_paint(word, code)}{_dim(_duration(seconds))}"
    return f"{line}  {_dim(detail)}" if detail else line


def verdict(name: str, codes: Sequence[int], seconds: float) -> str:
    """Render an aggregate's closing line: the answer in one line.

    Args:
        name: The target the line reports on.
        codes: Each step's status, in the order they ran.
        seconds: Wall time for the whole target.

    Returns:
        A single line naming how many steps passed, how many did not, and
        under which word - so a reader who scrolled past the rows still gets
        the verdict, and one who reads only the last line gets it too.
    """
    passed = sum(1 for code in codes if code == OK)
    parts = [f"{passed} ok"]
    for code in sorted({code for code in codes if code != OK}):
        count = sum(1 for other in codes if other == code)
        parts.append(_paint(f"{count} {status_word(code)}", code))
    worst = next((code for code in codes if code != OK), OK)
    summary = ", ".join(parts)
    return f"  {_paint(name, worst)}: {summary} in {seconds:.1f}s"


def replay(argv: Sequence[str], output: str) -> None:
    """Print a failed step's command and everything it produced.

    Captured output is replayed verbatim, which is what keeps suppression safe
    under ``GITHUB_ACTIONS``: :mod:`dev.ci_formats` makes a failing tool emit
    ``::error`` annotations on stdout, and replaying them here annotates the
    pull request exactly as streaming them would have. A passing tool emits no
    annotations, so nothing is lost by not hearing from it.

    Args:
        argv: The command that failed, printed so it can be re-run by hand.
        output: Its combined stdout and stderr.
    """
    print(f"$ {' '.join(argv)}", flush=True)
    if output:
        sys.stdout.write(output if output.endswith("\n") else f"{output}\n")
        sys.stdout.flush()
