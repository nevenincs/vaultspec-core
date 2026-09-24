"""Guards on what initializing this repository is allowed to do.

`just init` runs on every fresh worktree, including ones several writers share.
A git hook installed there makes every commit stash and restore the worktree's
unstaged changes, which loses any edit that lands mid-commit, so `init` must
never install one.
"""

from __future__ import annotations

import pytest

from dev.init.plan import PHASE_PLAN, PREFLIGHT

pytestmark = [pytest.mark.unit]

_HOOK_INSTALLERS = ("prek", "pre-commit", "dev.init.hooks")


def test_no_init_step_installs_a_git_hook() -> None:
    steps = [
        *PREFLIGHT,
        *(step for phase in PHASE_PLAN.values() for step in phase.steps),
    ]

    offenders = [
        step.name
        for step in steps
        if any(installer in step.argv for installer in _HOOK_INSTALLERS)
    ]

    assert offenders == [], f"init steps that install a git hook: {offenders}"
