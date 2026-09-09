"""Process-execution primitives shared by every development verb.

Each step type below is a small, declarative description of one action. They
are data rather than code so :mod:`dev.toolchain` can state the toolchain as a
table, and so the platform-specific parts - executable resolution, Docker
fallback, environment overlay - are implemented once here instead of being
re-expressed in each recipe.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from dev import ci_formats, reporting
from dev.exit_codes import TOOL_MISSING as _TOOL_MISSING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Re-exported from :mod:`dev.exit_codes`, which is the fleet-wide statement of
#: what every status means. Named here too because every caller in this module
#: already reads it from here, and the contract must have exactly one source.
TOOL_MISSING = _TOOL_MISSING


@dataclass(frozen=True)
class Cmd:
    """A single subprocess invocation.

    Args:
        argv: The full argument vector, already split. Never a shell string -
            passing a list is what keeps quoting identical on every platform.
        env: Environment variables overlaid on the inherited environment.
    """

    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class ToolOrDocker:
    """An external tool, falling back to its Docker image when absent.

    ``taplo``, ``lychee``, and ``actionlint`` are native binaries rather than
    Python packages, so they cannot be pinned in the lockfile and may simply
    be missing. Rather than fail, the harness runs the pinned image with the
    working tree mounted at ``/repo``, which is also what CI does when it has
    not installed the binary directly.

    Args:
        tool: Executable name to look for on ``PATH``.
        argv: Arguments passed to the native executable.
        image: Docker image reference used when the executable is absent.
        docker_argv: Arguments passed to the container. Defaults to ``argv``,
            and differs only where the container needs repo-absolute paths.
    """

    tool: str
    argv: tuple[str, ...]
    image: str
    docker_argv: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Echo:
    """A section header printed between the steps of an aggregate target."""

    text: str


@dataclass(frozen=True)
class Ref:
    """A reference to another target within the same verb.

    Aggregates such as ``lint all`` are expressed as references rather than by
    repeating their steps, so a target and its use in an aggregate cannot drift
    apart.
    """

    target: str


Step = Cmd | ToolOrDocker | Echo | Ref


@dataclass(frozen=True)
class Completed:
    """What one step did: its status, its output, and how long it took.

    ``output`` is populated only when the step was captured. A streamed step
    has already written to the terminal, so there is nothing to hold - the
    field is empty for it, not lost.

    Args:
        argv: The command as it actually ran, after ``ci_formats`` augmented
            it. Held so a failure can be replayed with the real recipe rather
            than the one before the CI flags were added.
        code: The status the child exited with.
        output: Combined stdout and stderr, when captured.
        seconds: Wall time for the step.
    """

    argv: tuple[str, ...]
    code: int
    output: str = ""
    seconds: float = 0.0


def run(
    argv: Sequence[str],
    env: Mapping[str, str] | None = None,
    *,
    capture: bool = False,
) -> Completed:
    """Run one subprocess and report what it did.

    Args:
        argv: The argument vector to execute.
        env: Variables overlaid on the inherited environment.
        capture: When true the child's output is collected instead of
            streamed, and the command line is not echoed. The caller decides
            whether the reader ever sees either - see :mod:`dev.reporting`.

    Returns:
        A :class:`Completed` carrying the child exit code, or
        :data:`TOOL_MISSING` when the executable does not exist.
    """
    merged = {**os.environ, **(env or {})}
    # What a tool PRINTS is decided in one place, from the environment; unset,
    # this returns the command untouched. It never changes the exit status.
    argv = tuple(ci_formats.augment(argv, merged))
    if not capture:
        print(f"$ {' '.join(argv)}", flush=True)
    # A captured tool sees a pipe and turns its colour off, which would strip
    # the highlighting from the diagnostics replayed on failure - the one case
    # where they are read. Asking for it back is only honest at a terminal, so
    # the parent's own stream decides.
    if capture and reporting.colouring():
        merged.setdefault("FORCE_COLOR", "1")
    started = time.perf_counter()
    try:
        # `text=True` alone decodes with the LOCALE encoding, which is cp1252
        # on the Windows runners; a byte outside it then raises on the
        # pipe-reader thread and the captured output comes back empty. That is
        # the #321 fault, and it costs more here than it did there: this
        # buffer is the only record of why a step failed, so losing it would
        # turn a diagnosable failure into a bare status. `replace` keeps a
        # mis-encoded byte from destroying the rest of the evidence.
        completed = subprocess.run(
            list(argv),
            env=merged,
            check=False,
            capture_output=capture,
            text=capture,
            encoding="utf-8" if capture else None,
            errors="replace" if capture else None,
        )
    except FileNotFoundError:
        elapsed = time.perf_counter() - started
        message = f"{argv[0]} not found on PATH"
        if not capture:
            print(message, file=sys.stderr, flush=True)
        return Completed(argv, TOOL_MISSING, f"{message}\n", elapsed)
    output = f"{completed.stdout or ''}{completed.stderr or ''}" if capture else ""
    return Completed(argv, completed.returncode, output, time.perf_counter() - started)


def run_tool_or_docker(step: ToolOrDocker, *, capture: bool = False) -> Completed:
    """Run a native tool, or its Docker image when the tool is unavailable.

    Args:
        step: The tool description to execute.
        capture: Passed through to :func:`run`.

    Returns:
        A :class:`Completed` for whichever form ran, or one carrying
        :data:`TOOL_MISSING` when neither the tool nor Docker is present.
    """
    if shutil.which(step.tool):
        return run([step.tool, *step.argv], capture=capture)
    if shutil.which("docker"):
        mount = f"{Path.cwd()}:/repo"
        container_argv = step.docker_argv if step.docker_argv is not None else step.argv
        return run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                mount,
                "-w",
                "/repo",
                step.image,
                *container_argv,
            ],
            capture=capture,
        )
    message = f"{step.tool} not found and docker is unavailable"
    if not capture:
        print(message, file=sys.stderr, flush=True)
    return Completed((step.tool, *step.argv), TOOL_MISSING, f"{message}\n")


def uv_run(*argv: str) -> Cmd:
    """Build a command that runs a tool already present in the environment.

    ``--no-sync`` keeps ``uv run`` from re-resolving and rebuilding the project
    into ``.venv``. That rebuild fails on Windows whenever a resident process -
    an MCP server, an editor, another agent's session - holds one of the
    console-script executables open, so every recipe that merely *uses* the
    environment goes through here. The recipes whose purpose is to *change* the
    environment (``uv sync``, ``uv lock``, ``uv build``) call ``uv`` directly.

    Args:
        *argv: The command and arguments to run inside the environment.

    Returns:
        The corresponding :class:`Cmd`.
    """
    return Cmd(("uv", "run", "--no-sync", *argv))
