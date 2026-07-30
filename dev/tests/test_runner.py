"""Behavioural guards for the harness's process-execution primitives.

:mod:`dev.runner` exists to make the platform-varying parts of running a tool -
executable resolution, environment overlay, a binary that simply is not
installed - behave identically everywhere. Substituting anything for a real
process here would test the substitute rather than the property, so every
assertion below drives a genuine subprocess and reads its genuine exit code.

The exit code is the contract the rest of the harness is built on: ``just`` and
CI both decide pass or fail from what these functions return.
"""

from __future__ import annotations

import os
import sys

import pytest

from dev.runner import TOOL_MISSING, Cmd, ToolOrDocker, run, run_tool_or_docker, uv_run

pytestmark = pytest.mark.unit

#: Environment variable used to prove the overlay reaches the child. Named for
#: this test module so an inherited value can never make the assertion vacuous.
PROBE = "DEV_HARNESS_ENV_PROBE"


def test_run_reports_a_successful_child_as_zero() -> None:
    """A step that succeeds returns 0 rather than the truthy exit convention."""
    assert run((sys.executable, "-c", "pass")) == 0


def test_run_propagates_the_child_exit_code() -> None:
    """A failing step surfaces its own code, not a flattened 1.

    Targets chain by propagating this value, so collapsing it would erase the
    distinction between a lint finding and a missing tool.
    """
    assert run((sys.executable, "-c", "raise SystemExit(3)")) == 3


def test_run_overlays_env_onto_the_inherited_environment() -> None:
    """The overlay adds variables without discarding what was inherited.

    ``UTF8`` in :mod:`dev.toolchain` relies on both halves: complexipy needs
    ``PYTHONIOENCODING`` added, and it needs ``PATH`` to survive.
    """
    assert PROBE not in os.environ, f"{PROBE} must not be set before the overlay"
    probe = (
        "import os, sys; "
        f"sys.exit(0 if os.environ.get({PROBE!r}) == 'overlaid' "
        "and os.environ.get('PATH') else 1)"
    )
    assert run((sys.executable, "-c", probe), {PROBE: "overlaid"}) == 0
    assert PROBE not in os.environ, "the overlay must not leak into this process"


def test_run_returns_tool_missing_for_an_absent_executable() -> None:
    """A missing binary is reported as 127 rather than raising.

    The harness runs tools that may genuinely not be installed; raising here
    would abort an aggregate target instead of failing one step of it.
    """
    assert run(("dev-harness-no-such-executable",)) == TOOL_MISSING


def test_uv_run_builds_a_no_sync_invocation() -> None:
    """Every environment-using step goes through ``uv run --no-sync``."""
    assert uv_run("pytest", "-q") == Cmd(("uv", "run", "--no-sync", "pytest", "-q"))


def test_tool_or_docker_runs_the_native_tool_when_it_resolves() -> None:
    """A resolvable tool runs directly and its exit code propagates.

    The image reference is deliberately unpullable: reaching Docker at all
    would fail the test rather than quietly pass through the fallback.
    """
    step = ToolOrDocker(
        sys.executable,
        ("-c", "raise SystemExit(6)"),
        "dev-harness.invalid/never-pulled:latest",
    )
    assert run_tool_or_docker(step) == 6
