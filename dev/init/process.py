"""Running a bootstrap step, and reading what its failure means.

The interesting part is not the subprocess call, it is
:func:`classify`. A bootstrap step fails for reasons that need different
remedies from different people, and a caller that cannot tell them apart can
only say "initialization failed":

* the workstation is missing a tool, and a person must install it;
* the lockfile and the project metadata disagree, and a commit must fix it;
* an editor or an MCP server is holding ``.venv/Scripts`` open, and the remedy
  is to close it and re-run - nothing is wrong with the repository at all.

The third case is the one that motivated a separate code. On Windows it is
routine, it is invisible in the tool's own error text unless you know the
phrasing to look for, and treating it as a build failure sends people hunting
for a defect that does not exist.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Final

from dev.exit_codes import (
    DRIFT,
    INIT_HOST_TOOL_MISSING,
    INIT_LOCKED,
    INIT_STEP_FAILED,
    OK,
)
from dev.init.contract import DONE, FAILED, StepResult

if TYPE_CHECKING:
    from pathlib import Path

    from dev.init.contract import Step

#: How many trailing lines of a failed step's output the report carries. Enough
#: to hold a Python traceback's final frames or a resolver's conflict summary,
#: short enough that a report of a fully failed run stays readable.
TAIL_LINES: Final = 40

#: Phrases that mean "another live process is holding this environment open".
#: Windows reports it four different ways depending on which layer noticed, and
#: uv, pip and the OS each phrase it differently. Matching on text is
#: unattractive and is nonetheless the only signal available: the status code
#: is an undifferentiated 1 or 2 in every one of these cases.
_LOCKED_MARKERS: Final[tuple[str, ...]] = (
    "being used by another process",
    "access is denied",
    "os error 32",
    "permission denied",
    "failed to remove file",
    "text file busy",
    "already owns",
    "refusing to mutate a virtualenv",
)

#: Phrases that mean "the lockfile no longer matches the project metadata".
#: These are drift, not a broken step: the environment is fine and a committed
#: file is wrong, so the remedy is a lock refresh rather than a re-run.
_DRIFT_MARKERS: Final[tuple[str, ...]] = (
    "the lockfile is not up-to-date",
    "the lock file is not up-to-date",
    "lockfile is out of date",
    "does not match the requirements",
    "`uv lock --check` failed",
    "npm ci` can only install packages when your package.json and package-lock.json",
)

#: Phrases that mean the executable itself is absent.
_MISSING_MARKERS: Final[tuple[str, ...]] = (
    "is not recognized as an internal or external command",
    "command not found",
    "no such file or directory",
    "cannot find the path specified",
)


def resolve(command: str) -> str | None:
    """Return the absolute path of an executable, or ``None``.

    This exists because of Windows. `npm`, `npx` and `mise` ship as `.cmd`
    shims there, and ``CreateProcess`` - which is what a shell-less
    :func:`subprocess.run` uses - will not find them from a bare name the way a
    shell would. The failure is a bare ``FileNotFoundError`` that reads exactly
    like "npm is not installed" on a machine where npm is plainly installed.

    Resolving through :func:`shutil.which` first, which honours ``PATHEXT``,
    is what keeps one shell-less implementation working identically on
    `cmd.exe`, `pwsh` and `sh`.

    Args:
        command: The executable name.

    Returns:
        The resolved path, or ``None`` when it is genuinely not on ``PATH``.
    """
    return shutil.which(command)


def tail(text: str, lines: int = TAIL_LINES) -> str:
    """Return the last lines of a process's output.

    Args:
        text: The captured output.
        lines: How many trailing lines to keep.

    Returns:
        The tail, with trailing whitespace stripped.
    """
    kept = text.rstrip().splitlines()[-lines:]
    return "\n".join(kept)


def classify(code: int, output: str) -> int:
    """Map a failed step onto the fleet exit-code contract.

    Args:
        code: The status the step exited with.
        output: Everything the step wrote.

    Returns:
        The contract code this failure should surface as. See
        :mod:`dev.exit_codes`; the numbers themselves live there and are not
        restated here.
    """
    if code == 0:
        return 0
    haystack = output.lower()
    if any(marker in haystack for marker in _LOCKED_MARKERS):
        return INIT_LOCKED
    if any(marker in haystack for marker in _DRIFT_MARKERS):
        return DRIFT
    if any(marker in haystack for marker in _MISSING_MARKERS):
        return INIT_HOST_TOOL_MISSING
    return INIT_STEP_FAILED


def run(step: Step, *, cwd: Path, echo: bool = True) -> tuple[StepResult, int]:
    """Execute one step and record what it did.

    Output is captured rather than inherited so the report can carry a tail of
    it, and is echoed to stderr as it is captured so a human watching a long
    ``uv sync`` is not staring at a silent terminal.

    Args:
        step: The step to run.
        cwd: The worktree root to run it in.
        echo: Whether to relay the step's output to stderr.

    Returns:
        The step's result, and the contract code its failure maps onto (0 when
        it succeeded or when it failed and was advisory).
    """
    started = time.monotonic()
    executable = resolve(step.argv[0])
    if executable is None:
        return (
            StepResult(
                name=step.name,
                argv=step.argv,
                status=DONE if step.advisory else FAILED,
                exit_code=INIT_HOST_TOOL_MISSING,
                duration_ms=0,
                output_tail=f"{step.argv[0]}: not found on PATH",
                advisory=step.advisory,
            ),
            OK if step.advisory else INIT_HOST_TOOL_MISSING,
        )
    argv = [executable, *step.argv[1:]]
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=step.timeout,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        code = completed.returncode
    except FileNotFoundError:
        output = f"{step.argv[0]}: command not found"
        code = INIT_HOST_TOOL_MISSING
    except subprocess.TimeoutExpired:
        output = f"timed out after {step.timeout} seconds"
        code = INIT_STEP_FAILED
    except OSError as exc:  # pragma: no cover - platform-specific spawn failure
        output = f"{step.argv[0]}: {exc}"
        code = INIT_STEP_FAILED

    duration = int((time.monotonic() - started) * 1000)
    if echo and output.strip():
        print(output.rstrip(), file=sys.stderr, flush=True)
    result = StepResult(
        name=step.name,
        argv=step.argv,
        status=DONE if code == 0 or step.advisory else FAILED,
        exit_code=code,
        duration_ms=duration,
        output_tail=tail(output) if code != 0 else "",
        advisory=step.advisory,
    )
    if code == 0 or step.advisory:
        return result, 0
    return result, classify(code, output)
