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
from typing import assert_never

from dev.exit_codes import advisory_result, selection_result
from dev.runner import Cmd, Echo, Ref, ToolOrDocker, run, run_tool_or_docker
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


def _execute(verb: Verb, target: Target) -> int:
    """Run one target's steps and return the resulting exit code.

    Args:
        verb: The owning verb, used to resolve :class:`~dev.runner.Ref` steps.
        target: The target to execute.

    Returns:
        For an advisory target, 0 when its tools ran (findings and all) and
        ADVISORY_BROKEN when one failed to run. Otherwise the code of the first
        failing step (or of the last step when none failed).
    """
    worst = 0
    for step in target.steps:
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
                code = _execute(verb, referenced)
            case ToolOrDocker():
                code = run_tool_or_docker(step)
            case Cmd():
                code = run(step.argv, step.env)
            case _:
                assert_never(step)

        if code != 0:
            # FIRST non-zero wins. An aggregate that keeps going reports the
            # status of the earliest thing that broke, because that is the one
            # whose failure may explain the rest.
            worst = worst or code
            if not target.keep_going:
                break

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
