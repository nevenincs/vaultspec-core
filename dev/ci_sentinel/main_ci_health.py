#!/usr/bin/env python
"""Decide whether ``main``'s tip commit actually received a CI verdict.

The repository's ruleset lists ten required status checks, but required checks
gate *pull request merges* only - they say nothing about a direct push, and
direct pushes are how most commits reach ``main`` here. The push-triggered CI
run is therefore the only thing standing between a direct push and an
unvalidated ``main``, and a run that never starts is indistinguishable from one
that passed unless something looks.

Three shapes have to be caught, and only the third is obvious:

- a run that completed badly (``failure``),
- a run that ended without ever running (``startup_failure``, ``cancelled``),
- **a run that was never created at all**, which has no record to inspect and
  so cannot be found by looking at runs. It is found by noticing that a commit
  old enough to have been judged has no verdict.

The judgement lives here rather than in the workflow's shell because it has
edge cases worth testing - a commit pushed seconds ago has no run yet and is
not a fault, and a long lane still in flight is not a fault either. Network
access stays in the caller: this module is handed the run list and returns a
verdict, so every branch below is reachable in a test.

Usage::

    gh api "repos/$REPO/actions/workflows/ci.yml/runs?head_sha=$SHA" \
      | python dev/ci_sentinel/main_ci_health.py --commit-age-minutes 130

Exit code 0 means healthy or not-yet-judged; 1 means ``main`` is carrying a
commit that CI never validated.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Literal

#: How long a commit may sit without a completed CI verdict before that counts
#: as a fault rather than a run still in flight. The slowest lane in this
#: repository's CI takes about half an hour, so this is generous on purpose: a
#: sentinel that cries wolf during a normal run gets muted, and a muted
#: sentinel is worth less than none.
DEFAULT_GRACE_MINUTES = 90

#: Run statuses that mean GitHub has not finished with this run yet.
IN_FLIGHT = frozenset({"queued", "in_progress", "waiting", "requested", "pending"})

State = Literal["healthy", "pending", "unhealthy"]


@dataclass(frozen=True)
class Verdict:
    """The sentinel's finding, and the sentence a human should read."""

    state: State
    reason: str

    @property
    def exit_code(self) -> int:
        """Non-zero only when ``main`` is genuinely unvalidated."""
        return 1 if self.state == "unhealthy" else 0


def classify(
    runs: list[dict[str, Any]],
    commit_age_minutes: float,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
) -> Verdict:
    """Judge one commit's CI runs.

    Args:
        runs: CI workflow runs for the commit, as the GitHub API returns them.
        commit_age_minutes: How long ago the commit landed.
        grace_minutes: How long a commit may go unjudged before it is a fault.

    Returns:
        The verdict, whose ``state`` is ``healthy`` when some run succeeded,
        ``pending`` when a verdict is still legitimately outstanding, and
        ``unhealthy`` when the commit is old enough that no verdict is coming.
    """
    for run in runs:
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            return Verdict("healthy", "CI succeeded for main's tip")

    in_flight = [run for run in runs if run.get("status") in IN_FLIGHT]
    if in_flight:
        return Verdict("pending", f"{len(in_flight)} CI run(s) still in flight")

    if not runs:
        if commit_age_minutes < grace_minutes:
            return Verdict(
                "pending",
                f"no CI run yet, but the commit is only "
                f"{commit_age_minutes:.0f}m old (grace {grace_minutes}m)",
            )
        return Verdict(
            "unhealthy",
            f"no CI run was ever created for main's tip, "
            f"{commit_age_minutes:.0f}m after it landed",
        )

    # Every run finished and none succeeded. `startup_failure` lands here, and
    # it is the shape that started this: zero jobs, zero logs, zero duration.
    conclusions = sorted({str(run.get("conclusion")) for run in runs})
    return Verdict(
        "unhealthy",
        f"CI did not succeed for main's tip; conclusions: {', '.join(conclusions)}",
    )


def _commit_age_minutes(value: str) -> float:
    age = float(value)
    if age < 0:
        raise argparse.ArgumentTypeError("commit age cannot be negative")
    return age


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit-age-minutes",
        type=_commit_age_minutes,
        required=True,
        help="how long ago main's tip commit landed",
    )
    parser.add_argument(
        "--grace-minutes",
        type=int,
        default=DEFAULT_GRACE_MINUTES,
        help="how long a commit may go unjudged before that is a fault",
    )
    args = parser.parse_args(argv)

    payload: dict[str, Any] = json.load(sys.stdin)
    runs: list[dict[str, Any]] = payload.get("workflow_runs", [])

    verdict = classify(runs, args.commit_age_minutes, args.grace_minutes)
    print(f"{verdict.state}: {verdict.reason}")
    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
