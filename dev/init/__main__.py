"""The ``python -m dev.init`` entry point.

Usage, one form per justfile recipe::

    python -m dev.init all      # just init
    python -m dev.init python   # just init-python
    python -m dev.init node     # just init-node
    python -m dev.init tools    # just init-tools
    python -m dev.init check    # just init-check

The recipes are argument-free, so the two modifiers are environment variables
as well as flags: ``VAULTSPEC_INIT_JSON=1`` for the NDJSON event stream and
``VAULTSPEC_INIT_FORCE=1`` to ignore the stamp.

Why `init` is fail-fast, when the fleet's `-all` aggregates are not
--------------------------------------------------------------------

The fleet rule is that an ``-all`` aggregate runs every step and exits with the
first non-zero status, because those aggregates chain INDEPENDENT INSPECTORS: a
type error does not stop the markdown linter from having something true to say,
and a developer wants the whole list in one pass.

`init` is the opposite shape, and follows the opposite rule deliberately. Its
phases are a DEPENDENCY CHAIN that builds one artifact. ``init-tools`` installs
git hooks and enrolls the framework by running executables out of the
environment ``init-python`` creates; in ``vaultspec-dashboard`` those same hooks
lint the SPA that ``init-node`` restores. Running ``init-tools`` after
``init-python`` failed does not produce a second independent finding - it
produces a cascade of "command not found" that buries the one real cause, and
it produces it slowly.

So `init` stops at the first failing phase. What it does NOT do is stop
REPORTING: the phases that did not run are recorded as ``skipped`` with the
upstream failure named, so the report is always complete and a reader can see
what was and was not attempted. Within a phase the same reasoning applies at
finer grain - ``uv sync`` cannot succeed before ``uv venv`` - and steps stop at
the first failure too. Advisory steps are exempt in both directions: they are
diagnosis, they never gate, and a phase continues past one that failed.

The consequence a caller should rely on: a non-zero `init` names ONE cause.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dev.exit_codes import INIT_HOST_TOOL_MISSING, INIT_STALE, OK
from dev.init import plan
from dev.init.contract import (
    DONE,
    FAILED,
    FORCE_ENV,
    FRESH,
    JSON_ENV,
    PHASES,
    SKIPPED,
    STALE,
    Emitter,
    Outcome,
    Phase,
    PhaseResult,
    StepResult,
    build_report,
)
from dev.init.probe import check_all
from dev.init.process import run as run_step
from dev.init.stamp import (
    is_current,
    phase_digest,
    report_path,
    staleness,
)
from dev.init.stamp import (
    read as read_stamp,
)
from dev.init.stamp import (
    write as write_stamp,
)

#: The selectors the justfile recipes pass, mapped to the phases they run.
SELECTIONS = {
    "all": PHASES,
    "python": ("python",),
    "node": ("node",),
    "tools": ("tools",),
}


def _repo_root() -> Path:
    """Return the worktree root.

    Returns:
        The directory two levels above this file, which is the repository root
        for ``dev/init/__main__.py`` in every repository in the fleet.
    """
    return Path(__file__).resolve().parents[2]


def _truthy(name: str) -> bool:
    """Return whether an environment variable is set to something affirmative.

    Args:
        name: The variable's name.

    Returns:
        True for ``1``, ``true``, ``yes`` and ``on``, case-insensitively.
    """
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _preflight(
    repo_root: Path,
    emitter: Emitter,
) -> tuple[list[StepResult], int, list[str]]:
    """Run the steps that must happen before any phase, and probe the host.

    Two things live here rather than in a phase. The first is `.env`
    materialization: ``vaultspec-a2a``'s justfile sets ``dotenv-load``, so a
    worktree without a `.env` is under-configured for `just` itself - including
    for the very `init` that would have created it. Making it a preflight means
    every entry point fixes it, not only ``init-tools``.

    The second is the host-tool probe. A missing `uv` or `node` is not a step
    failure to be discovered halfway through a sync; it is a precondition, and
    reporting the complete list of what the workstation lacks before touching
    anything is worth more than failing fast on the first one.

    Args:
        repo_root: The worktree root.
        emitter: The run's output channels.

    Returns:
        The preflight step results, the contract exit code (0 when the host is
        adequate), and the remediation lines for anything missing.
    """
    remediation: list[str] = []
    results: list[StepResult] = []

    findings = check_all(plan.REQUIREMENTS)
    blocking = [item for item in findings if not item.ok and not item.advisory]
    for finding in findings:
        emitter.say(f"  host: {finding.message}")
        emitter.event(
            "host-tool",
            command=finding.command,
            ok=finding.ok,
            found=finding.found,
            advisory=finding.advisory,
        )
        if not finding.ok:
            remediation.append(finding.message)
    if blocking:
        return results, INIT_HOST_TOOL_MISSING, remediation

    for step in plan.PREFLIGHT:
        emitter.say(f"  {step.summary}")
        result, code = run_step(step, cwd=repo_root)
        results.append(result)
        emitter.event("step", phase="preflight", **result.as_dict())
        if code != OK:
            remediation.append(
                f"preflight step '{step.name}' failed: {' '.join(step.argv)}",
            )
            return results, code, remediation
    return results, OK, remediation


def _run_phase(
    repo_root: Path,
    phase: Phase,
    emitter: Emitter,
    *,
    force: bool,
) -> PhaseResult:
    """Run one phase, or establish that it does not need running.

    Args:
        repo_root: The worktree root.
        phase: The phase to run.
        emitter: The run's output channels.
        force: Whether to ignore the stamp.

    Returns:
        The phase's result.
    """
    if not phase.steps:
        reason = phase.skip_reason or "nothing to do in this repository"
        emitter.say(f"init-{phase.name}: skipped - {reason}")
        emitter.event("phase", name=phase.name, status=SKIPPED, reason=reason)
        return PhaseResult(name=phase.name, status=SKIPPED, reason=reason)

    if not force and is_current(repo_root, phase, read_stamp(repo_root)):
        reason = "already initialized; inputs unchanged"
        emitter.say(f"init-{phase.name}: up to date")
        emitter.event("phase", name=phase.name, status=FRESH, reason=reason)
        return PhaseResult(name=phase.name, status=FRESH, reason=reason)

    emitter.say(f"init-{phase.name}: {phase.summary}")
    emitter.event("phase-start", name=phase.name)
    result = PhaseResult(name=phase.name, status=DONE)
    for step in phase.steps:
        emitter.say(f"  $ {' '.join(step.argv)}")
        step_result, code = run_step(step, cwd=repo_root)
        result.steps.append(step_result)
        emitter.event("step", phase=phase.name, **step_result.as_dict())
        if code != OK:
            result.status = FAILED
            result.exit_code = code
            result.reason = f"step '{step.name}' failed: exit {step_result.exit_code}"
            emitter.say(f"init-{phase.name}: FAILED - {result.reason}")
            emitter.event(
                "phase",
                name=phase.name,
                status=FAILED,
                reason=result.reason,
                exit_code=code,
            )
            return result

    emitter.event("phase", name=phase.name, status=DONE, reason="")
    return result


def _check(
    repo_root: Path,
    emitter: Emitter,
) -> tuple[list[PhaseResult], int, list[str]]:
    """Report whether the worktree is initialized, changing nothing.

    Args:
        repo_root: The worktree root.
        emitter: The run's output channels.

    Returns:
        The per-phase results, the exit code, and the remediation lines.
    """
    stale = dict(staleness(repo_root, plan.PHASE_PLAN.values()))
    results: list[PhaseResult] = []
    for name in PHASES:
        phase = plan.PHASE_PLAN[name]
        if not phase.steps:
            status, reason = SKIPPED, phase.skip_reason or "nothing to do"
        elif name in stale:
            status, reason = STALE, stale[name]
        else:
            status, reason = FRESH, "up to date"
        emitter.say(f"init-{name}: {status}{' - ' + reason if reason else ''}")
        emitter.event("phase", name=name, status=status, reason=reason)
        results.append(PhaseResult(name=name, status=status, reason=reason))
    if stale:
        return (
            results,
            INIT_STALE,
            [f"run `just init` ({name}: {why})" for name, why in stale.items()],
        )
    return results, OK, []


def main(argv: list[str] | None = None) -> int:
    """Initialize this worktree, or report on it.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        A code from :mod:`dev.exit_codes`. See this module's docstring for why
        a failure names exactly one cause.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.init",
        description="Initialize this worktree so it is usable.",
    )
    parser.add_argument(
        "selection",
        choices=[*SELECTIONS, "check"],
        nargs="?",
        default="all",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit NDJSON events on stdout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore the idempotence stamp",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    emitter = Emitter(json_mode=args.json or _truthy(JSON_ENV))
    force = args.force or _truthy(FORCE_ENV)

    emitter.event("run-start", repo=repo_root.name, selection=args.selection)

    if args.selection == "check":
        checked, code, remediation = _check(repo_root, emitter)
        report = build_report(
            repo_root=repo_root,
            selection=["check"],
            phases=checked,
            outcome=Outcome(FRESH if code == OK else STALE, code),
            remediation=remediation,
        )
        _finish(repo_root, report, emitter, write_file=False)
        return code

    selection = SELECTIONS[args.selection]
    preflight, code, remediation = _preflight(repo_root, emitter)
    phases: list[PhaseResult] = []
    if preflight:
        phases.append(
            PhaseResult(
                name="preflight",
                status=FAILED if code != OK else DONE,
                reason="" if code == OK else "a preflight step failed",
                steps=preflight,
                exit_code=code,
            )
        )

    if code == OK:
        digests = dict(read_stamp(repo_root))
        failure = ""
        for name in selection:
            phase = plan.PHASE_PLAN[name]
            if failure:
                reason = f"not attempted: init-{failure} failed"
                emitter.say(f"init-{name}: skipped - {reason}")
                emitter.event("phase", name=name, status=SKIPPED, reason=reason)
                phases.append(PhaseResult(name=name, status=SKIPPED, reason=reason))
                continue
            result = _run_phase(repo_root, phase, emitter, force=force)
            phases.append(result)
            if result.status == FAILED:
                failure = name
                code = result.exit_code
                remediation.append(result.reason)
            elif phase.steps:
                digests[name] = phase_digest(repo_root, phase)
        write_stamp(repo_root, digests)

    status = DONE if code == OK else FAILED
    report = build_report(
        repo_root=repo_root,
        selection=list(selection),
        phases=phases,
        outcome=Outcome(status, code),
        remediation=remediation,
    )
    _finish(repo_root, report, emitter, write_file=True)
    if code == OK:
        emitter.say(f"init: {repo_root.name} is ready.")
    return code


def _finish(
    repo_root: Path,
    report: dict,
    emitter: Emitter,
    *,
    write_file: bool,
) -> None:
    """Write the report and announce where it went.

    Args:
        repo_root: The worktree root.
        report: The assembled report.
        emitter: The run's output channels.
        write_file: Whether to persist the report. ``init-check`` does not,
            because it is contractually non-mutating and a report file is a
            mutation like any other.
    """
    path = report_path(repo_root)
    if write_file:
        try:
            payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
            path.write_text(payload, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - unwritable filesystem
            emitter.say(f"init: could not write the report to {path}: {exc}")
        else:
            emitter.say(f"init: report written to {path}")
    written = str(path) if write_file else None
    emitter.event("run-end", report=report, report_path=written)
    for line in report["remediation"]:
        emitter.say(f"  -> {line}")


if __name__ == "__main__":
    sys.exit(main())
