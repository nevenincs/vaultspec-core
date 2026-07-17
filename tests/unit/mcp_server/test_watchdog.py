"""Tests for the Windows client-PID stdio watchdog.

Every test drives real processes and real pipes: children are spawned with
``sys.executable``, stdin pipes are genuine OS pipes, and liveness is
observed through the same Win32 process-handle semantics the watchdog
relies on. No mocks, stubs, or skips: on non-Windows platforms the same
tests assert the module's genuine fail-open contract (resolver yields no
PID, arming declines) instead of being deselected.

The end-to-end test reproduces the leak scenario from the field report: a
client dies while a sibling process still holds the write end of the
server's stdin pipe, so EOF can never arrive and only the watchdog can
reap the server.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vaultspec_core.mcp_server.watchdog import (
    arm_client_watchdog,
    resolve_stdin_client_pid,
)

pytestmark = pytest.mark.unit

_RESOLVER_SNIPPET = (
    "from vaultspec_core.mcp_server.watchdog import resolve_stdin_client_pid;"
    "print(resolve_stdin_client_pid(), flush=True)"
)


def _wait_for_pid_exit(pid: int, timeout: float) -> bool:
    """Wait until the process identified by *pid* exits (Windows only).

    Uses ``OpenProcess``/``WaitForSingleObject`` rather than ``os.kill``,
    which on Windows terminates the target instead of probing it.

    Returns:
        ``True`` when the process exited within *timeout* seconds (or was
        already gone), ``False`` when it is still alive at the deadline.
    """
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    synchronize = 0x0010_0000
    handle = kernel32.OpenProcess(synchronize, False, ctypes.c_ulong(pid))
    if not handle:
        return True
    try:
        result = kernel32.WaitForSingleObject(
            ctypes.c_void_p(handle), int(timeout * 1000)
        )
        return result == 0
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def test_resolver_identifies_pipe_creating_process() -> None:
    """A child resolving its stdin pipe reports the pipe creator's PID.

    ``subprocess.PIPE`` creates the stdin pipe inside this test process, so
    the child's resolver must return this process's PID on Windows and the
    fail-open ``None`` elsewhere.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _RESOLVER_SNIPPET],
        stdin=subprocess.PIPE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    resolved = proc.stdout.strip()
    if sys.platform == "win32":
        assert resolved == str(os.getpid())
    else:
        assert resolved == "None"


def test_resolver_sees_through_wrapper_processes() -> None:
    """Wrapper depth does not change the resolved client PID.

    An intermediary process (standing in for ``uv``/launcher wrappers)
    passes its inherited stdin straight to a grandchild; the grandchild's
    resolver must still report this test process, not the intermediary.
    """
    intermediary = (
        "import subprocess, sys;"
        f"sys.exit(subprocess.run([sys.executable, '-c', {_RESOLVER_SNIPPET!r}],"
        " stdin=sys.stdin).returncode)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", intermediary],
        stdin=subprocess.PIPE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    resolved = proc.stdout.strip()
    if sys.platform == "win32":
        assert resolved == str(os.getpid())
    else:
        assert resolved == "None"


def test_non_pipe_stdin_fails_open(tmp_path: Path) -> None:
    """A file-backed stdin is not a pipe: resolver and arming both decline."""
    snippet = (
        "from vaultspec_core.mcp_server.watchdog import"
        " arm_client_watchdog, resolve_stdin_client_pid;"
        "print(resolve_stdin_client_pid(), arm_client_watchdog(), flush=True)"
    )
    stdin_file = tmp_path / "stdin.txt"
    stdin_file.write_text("not a pipe\n", encoding="utf-8")
    with stdin_file.open("rb") as fh:
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            stdin=fh,
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "None False"


def test_in_process_contract_on_this_platform() -> None:
    """Direct calls honor the platform contract without side effects.

    The contract is identical on every platform: POSIX returns the hard
    ``None``, and under pytest on Windows the captured stdin is not a
    client-owned pipe, so arming must decline rather than spawn a watchdog
    thread against a live process this test cannot control.
    """
    assert resolve_stdin_client_pid() is None
    assert arm_client_watchdog() is False


def test_armed_worker_exits_when_dead_client_pid_signals() -> None:
    """Arming against an already-exited client exits the worker immediately.

    The test holds the victim's ``Popen`` handle so the kernel keeps the
    process object alive after exit: ``OpenProcess`` then succeeds and the
    wait fires at once. On POSIX the override path declines and the worker
    reports it stayed up.
    """
    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)

    worker_code = textwrap.dedent(
        f"""
        import sys, time
        from vaultspec_core.mcp_server.watchdog import arm_client_watchdog
        armed = arm_client_watchdog(client_pid={victim.pid})
        print(f"armed={{armed}}", flush=True)
        time.sleep(20)
        print("still-alive", flush=True)
        """
    )
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    elapsed = time.monotonic() - started
    if sys.platform == "win32":
        # The wait fires the instant it arms, so os._exit races (and usually
        # beats) the worker's own print: assert on the exit, not the output.
        assert proc.returncode == 0
        assert "still-alive" not in proc.stdout
        assert elapsed < 15, f"worker outlived a dead client by {elapsed:.1f}s"
    else:
        assert "armed=False" in proc.stdout
        assert "still-alive" in proc.stdout


def test_real_server_exits_when_client_dies_despite_leaked_pipe(
    tmp_path: Path,
) -> None:
    """End-to-end reproduction of the field leak, resolved by the watchdog.

    A client process creates the server's stdin pipe with an inheritable
    write end, spawns the real ``vaultspec_core.mcp_server.app`` module on
    the read end, and leaks the write end into a sibling sleeper. Killing
    the client leaves the pipe open (the sibling holds it), so stdin EOF
    cannot fire; only the client-PID watchdog can reap the server. On
    POSIX the watchdog declines by contract and this test instead proves
    the client script wiring itself is sound, exiting early.
    """
    if sys.platform != "win32":
        assert resolve_stdin_client_pid() is None
        return

    client_code = textwrap.dedent(
        f"""
        import os, subprocess, sys, time
        r, w = os.pipe()
        os.set_inheritable(w, True)
        server = subprocess.Popen(
            [sys.executable, "-m", "vaultspec_core.mcp_server.app"],
            stdin=r,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd={str(tmp_path)!r},
        )
        os.close(r)
        # The sleeper inherits the pipe write end (close_fds=False), so the
        # pipe stays open after this client dies: the leak scenario.
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            close_fds=False,
        )
        print(server.pid, flush=True)
        print(sleeper.pid, flush=True)
        time.sleep(3600)
        """
    )
    client = subprocess.Popen(
        [sys.executable, "-c", client_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert client.stdout is not None
        server_pid = int(client.stdout.readline())
        sleeper_pid = int(client.stdout.readline())

        # Give the server a moment to boot and arm before the client dies.
        time.sleep(5)
        client.kill()
        client.wait(timeout=60)

        try:
            assert _wait_for_pid_exit(server_pid, timeout=30), (
                "server survived its client; watchdog did not fire"
            )
        finally:
            subprocess.run(
                ["taskkill", "/PID", str(sleeper_pid), "/F"],
                capture_output=True,
            )
    finally:
        if client.poll() is None:
            client.kill()
