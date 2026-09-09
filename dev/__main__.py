"""The ``python -m dev`` entry point behind every justfile recipe.

Usage::

    python -m dev <verb> [target]
    python -m dev <verb> help
    python -m dev help

Exit codes are the point of this module: a gating target propagates the exit
code of whichever step failed, so ``just`` and CI both see the real result. An
advisory target suppresses its FINDINGS - and only its findings - because a
scan that yields leads rather than verdicts must not gate a build. A tool that
failed to RUN is a different event and always propagates, as
:data:`~dev.exit_codes.ADVISORY_BROKEN`: "reported nothing" is not "found
nothing".

``dev/EXIT-CODES.md`` is the canonical statement of the contract and
``dev/exit_codes.py`` its machine-readable form.
"""

from __future__ import annotations

import sys
import textwrap
import time
from typing import assert_never

from dev import reporting, testing
from dev.exit_codes import advisory_result, selection_result
from dev.runner import (
    Cmd,
    Completed,
    Echo,
    Ref,
    Step,
    ToolOrDocker,
    run,
    run_tool_or_docker,
)
from dev.toolchain import (
    DEFAULTS,
    VERBS,
    Target,
    Verb,
    find_verb,
    public_targets,
)


def _print_verb_help(verb: Verb) -> None:
    """Print a verb's usage, targets, and note.

    Args:
        verb: The verb whose help to render.
    """
    print(f"usage: just {verb.name} <target>")
    print(f"  {verb.summary}")
    print()
    width = max(len(name) for name in public_targets(verb))
    for target in verb.targets:
        if target.name.startswith("_"):
            continue
        flag = " (advisory)" if target.advisory and target.name != "all" else ""
        print(f"  {target.name:<{width}}  {target.summary}{flag}")
    if verb.note:
        print()
        print(
            textwrap.fill(
                verb.note, width=88, initial_indent="  ", subsequent_indent="  "
            )
        )


def _print_root_help() -> None:
    """Print the list of every verb."""
    print("usage: python -m dev <verb> [target]")
    print()
    width = max(len(verb.name) for verb in VERBS)
    for verb in VERBS:
        print(f"  {verb.name:<{width}}  {verb.summary}")
    print()
    print("  Run 'python -m dev <verb> help' for a verb's targets.")


def _labels(target: Target) -> list[str]:
    """Name every step of a target, positionally.

    Computed for the target as a whole rather than per step, because telling
    two colliding labels apart needs the commands they collide with - which is
    only knowable before the first one runs.

    Args:
        target: The target whose steps to name.

    Returns:
        One label per step. A :class:`~dev.runner.Ref` is named by the target
        it refers to, so an aggregate reads as the dimensions it composes.
    """
    commands: list[tuple[str, ...]] = []
    for step in target.steps:
        match step:
            case Ref() | Echo():
                commands.append(())
            case ToolOrDocker():
                commands.append((step.tool, *step.argv))
            case Cmd():
                commands.append(step.argv)
            case _:
                assert_never(step)
    labels = reporting.distinct_labels(commands)
    return [
        _step_label(step, command, label)
        for step, command, label in zip(target.steps, commands, labels, strict=True)
    ]


def _step_label(step: Step, command: tuple[str, ...], derived: str) -> str:
    """Prefer a name a step declared for itself over one derived from its argv.

    A `Ref` is named by the target it refers to and a test lane by the lane it
    declared; only a step that named itself nothing falls back to the guess.
    """
    if isinstance(step, Ref):
        return step.target
    lane = testing.lane_name(command)
    return f"pytest {lane}" if lane else derived


def _execute(
    verb: Verb,
    target: Target,
    *,
    emit_rows: bool = True,
    deferred: list[Completed] | None = None,
) -> int:
    """Run one target's steps, report what each did, and return the status.

    Every step contributes one verdict row whether its tool was heard from or
    not, so a reader learns that a step RAN from the harness rather than by
    inferring it from output the tool may not produce. A step that failed is
    additionally replayed in full - suppression is for clean passes only.

    Args:
        verb: The owning verb, used to resolve :class:`~dev.runner.Ref` steps.
        target: The target to execute.
        emit_rows: When false the steps report nothing individually and the
            caller renders one row for the target as a whole. Set by a
            :class:`~dev.runner.Ref`, so an aggregate reads as a list of the
            DIMENSIONS it composes rather than of every tool underneath them.
        deferred: Where to hand failures the caller must replay, used with
            ``emit_rows=False``. A nested failure belongs UNDER the row naming
            the dimension it came from, and that row is the caller's to print.

    Returns:
        For an advisory target, 0 when its tools ran (findings and all) and
        ADVISORY_BROKEN when one failed to run. Otherwise the code of the first
        failing step (or of the last step when none failed).
    """
    # A gate is quiet only when nothing asked to hear it: the verbose escape
    # hatch restores the streamed, echoed run the harness used to always do.
    capture = target.quiet_on_pass and not reporting.verbose()
    worst = 0
    codes: list[int] = []
    labels = _labels(target)
    started = time.perf_counter()

    for index, step in enumerate(target.steps):
        code, elapsed, detail = 0, 0.0, ""
        failures: list[Completed] = []
        match step:
            case Echo():
                print(f"\n{step.text}", flush=True)
                continue
            case Ref():
                referenced = verb.find(step.target)
                if referenced is None:
                    print(
                        f"internal error: {verb.name} references undefined target "
                        f"'{step.target}'",
                        file=sys.stderr,
                    )
                    return 1
                ref_started = time.perf_counter()
                code = _execute(verb, referenced, emit_rows=False, deferred=failures)
                elapsed = time.perf_counter() - ref_started
            case ToolOrDocker() | Cmd():
                completed = (
                    run_tool_or_docker(step, capture=capture)
                    if isinstance(step, ToolOrDocker)
                    else run(step.argv, step.env, capture=capture)
                )
                code, elapsed = completed.code, completed.seconds
                # A step that asked pytest for a record reports the population
                # it ran, because its exit code cannot: a lane that collected
                # three tests exits exactly like one that collected four
                # thousand.
                report = testing.declared_report(completed.argv)
                if report is not None:
                    detail = testing.describe(testing.read(report))
                if code != 0 and capture:
                    failures.append(completed)
            case _:
                assert_never(step)

        codes.append(code)
        if emit_rows:
            print(reporting.row(labels[index], code, elapsed, detail), flush=True)
            # After the row, never before it: the reader needs to know WHICH
            # step is speaking before they read what it said. A failure is
            # replayed in full - the command, and everything it printed.
            for failure in failures:
                reporting.replay(failure.argv, failure.output)
        elif deferred is not None:
            deferred.extend(failures)

        if code != 0:
            # FIRST non-zero wins. An aggregate that keeps going reports the
            # status of the earliest thing that broke, because that is the one
            # whose failure may explain the rest.
            worst = worst or code
            if not target.keep_going:
                break

    # One line that answers the question, for a target that asked more than one
    # thing. A single-step target already answered it in its own row.
    if emit_rows and len(codes) > 1:
        print(
            reporting.verdict(
                f"{verb.name} {target.name}", codes, time.perf_counter() - started
            ),
            flush=True,
        )

    worst = selection_result(worst)
    return advisory_result(worst, target.findings_codes) if target.advisory else worst


def main(argv: list[str] | None = None) -> int:
    """Dispatch a verb and target from the argument vector.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The process exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"help", "--help", "-h"}:
        _print_root_help()
        return 0

    verb_name, *rest = args
    verb = find_verb(verb_name)
    if verb is None:
        print(f"unknown verb: {verb_name}", file=sys.stderr)
        print(f"  verbs: {' '.join(v.name for v in VERBS)}", file=sys.stderr)
        return 1

    target_name = rest[0] if rest else DEFAULTS.get(verb.name, "all")

    if target_name in {"help", "--help", "-h"}:
        _print_verb_help(verb)
        return 0

    target = verb.find(target_name)
    if target is None or target.name.startswith("_"):
        print(f"unknown {verb.name} target: {target_name}", file=sys.stderr)
        print(f"  targets: {' '.join(public_targets(verb))}", file=sys.stderr)
        if verb.note:
            print(f"  {verb.note}", file=sys.stderr)
        return 1

    return _execute(verb, target)


if __name__ == "__main__":
    raise SystemExit(main())
