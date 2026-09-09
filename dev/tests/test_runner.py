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
    assert run((sys.executable, "-c", "pass")).code == 0


def test_run_propagates_the_child_exit_code() -> None:
    """A failing step surfaces its own code, not a flattened 1.

    Targets chain by propagating this value, so collapsing it would erase the
    distinction between a lint finding and a missing tool.
    """
    assert run((sys.executable, "-c", "raise SystemExit(3)")).code == 3


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
    assert run((sys.executable, "-c", probe), {PROBE: "overlaid"}).code == 0
    assert PROBE not in os.environ, "the overlay must not leak into this process"


def test_run_returns_tool_missing_for_an_absent_executable() -> None:
    """A missing binary is reported as 127 rather than raising.

    The harness runs tools that may genuinely not be installed; raising here
    would abort an aggregate target instead of failing one step of it.
    """
    assert run(("dev-harness-no-such-executable",)).code == TOOL_MISSING


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
    assert run_tool_or_docker(step).code == 6


def test_capture_collects_both_streams_without_printing_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A captured step returns its output instead of writing it out.

    Both streams are kept. A tool that reports findings on stderr and a tool
    that reports them on stdout are equally common, and a replay that showed
    only one half would suppress exactly the diagnosis it exists to preserve.
    """
    both = "import sys; print('out'); print('err', file=sys.stderr)"
    completed = run((sys.executable, "-c", both), capture=True)

    assert completed.code == 0
    assert "out" in completed.output
    assert "err" in completed.output
    assert capsys.readouterr().out == "", "a captured step must print nothing itself"


def test_capture_decodes_as_utf8_rather_than_the_locale() -> None:
    """Captured bytes decode as UTF-8 whatever the console codepage is.

    The captured buffer is the only record of why a step failed. Decoding it
    with the locale encoding loses that record on exactly the runs where it
    matters most - see `dev/guards/test_subprocess_capture_encoding.py`.
    """
    emit = "import sys; sys.stdout.buffer.write('… ✅'.encode('utf-8')); sys.exit(1)"
    completed = run((sys.executable, "-c", emit), capture=True)

    assert completed.code == 1
    assert "… ✅" in completed.output


def test_capture_survives_undecodable_bytes() -> None:
    """A byte that is not valid UTF-8 must not destroy the rest of the output.

    A harness step captures whatever a tool emits, including OS-level messages
    in the platform's own encoding. Raising here would return empty output and
    make a diagnosable failure look like a silent one.
    """
    emit = r"import sys; sys.stdout.buffer.write(b'before\x90after')"
    completed = run((sys.executable, "-c", emit), capture=True)

    assert completed.code == 0
    assert "before" in completed.output
    assert "after" in completed.output


def test_an_uncaptured_step_echoes_its_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Streaming keeps the echoed command line the harness has always printed."""
    run((sys.executable, "-c", "pass"))

    assert "$ " in capsys.readouterr().out


def test_a_missing_executable_is_reported_in_the_captured_output() -> None:
    """An absent tool explains itself through the buffer when captured.

    The message is the whole diagnosis for this status, so it has to travel by
    the same route as any other failure's output rather than to a stderr the
    caller has already decided not to show.
    """
    completed = run(("dev-harness-no-such-executable",), capture=True)

    assert completed.code == TOOL_MISSING
    assert "not found on PATH" in completed.output
