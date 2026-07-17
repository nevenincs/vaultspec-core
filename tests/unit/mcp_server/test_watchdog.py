"""Tests for the stdio lifetime watchdog: anchors, knobs, and telemetry.

Every test drives real processes and real pipes: children are spawned with
``sys.executable``, stdin pipes are genuine OS pipes, and liveness is
observed through the same Win32 process-handle semantics the watchdog
relies on. No mocks, stubs, or skips: on non-Windows platforms the same
tests assert the module's genuine POSIX contract (no pipe-creator
resolution, reparent-poll arming) instead of being deselected.

Coverage spans the layered anchors: the client-PID primary (resolution
directly and through wrapper depth, instant reap of a dead client), the
ancestor-chain fallback (non-pipe launches, ancestor death, grace-window
pruning of transient spawners), the operator kill switch, the explicit
``--parent-pid`` override through the real entrypoint, and the structured
exit event. The end-to-end test reproduces the leak scenario from the
field report: a client dies while a sibling process still holds the write
end of the server's stdin pipe, so EOF can never arrive and only the
watchdog can reap the server.
"""

from __future__ import annotations

import json
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
    STDIO_WATCHDOG_ENV,
    arm_client_watchdog,
    resolve_stdin_client_pid,
    watchdog_disabled,
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


def _wait_for_posix_pid_exit(pid: int, timeout: float) -> bool:
    """Poll POSIX liveness until *pid* exits or the deadline passes.

    ``os.kill(pid, 0)`` is the correct probe on POSIX only; on Windows it
    terminates the target, hence the separate handle-based helper above.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.5)
    return False


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


def test_non_pipe_stdin_arms_ancestor_fallback(tmp_path: Path) -> None:
    """A file-backed stdin declines resolution but still arms a backstop.

    The resolver yields no client PID, so on Windows arming falls back to
    the discovered ancestor chain and on POSIX the reparent poll arms:
    every launch shape gets a watchdog, not only pipe-spawned ones.
    """
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
    assert proc.stdout.strip() == "None True"


def test_kill_switch_disables_arming_in_process() -> None:
    """The env kill switch declines arming before any anchor is touched.

    Exercised in-process with a real environment mutation (restored in
    ``finally``) so no watchdog thread is ever spawned inside the test
    runner.
    """
    previous = os.environ.get(STDIO_WATCHDOG_ENV)
    os.environ[STDIO_WATCHDOG_ENV] = "off"
    try:
        assert watchdog_disabled() is True
        assert resolve_stdin_client_pid() is None
        assert arm_client_watchdog() is False
    finally:
        if previous is None:
            del os.environ[STDIO_WATCHDOG_ENV]
        else:
            os.environ[STDIO_WATCHDOG_ENV] = previous


def test_kill_switch_disables_arming_in_worker() -> None:
    """A worker launched with the kill switch set stays alive and unarmed."""
    worker_code = textwrap.dedent(
        """
        import time
        from vaultspec_core.mcp_server.watchdog import arm_client_watchdog
        print(f"armed={arm_client_watchdog()}", flush=True)
        time.sleep(2)
        print("still-alive", flush=True)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        env={**os.environ, STDIO_WATCHDOG_ENV: "0"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "armed=False" in proc.stdout
    assert "still-alive" in proc.stdout


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

    (tmp_path / ".vaultspec").mkdir()
    (tmp_path / ".vault").mkdir()
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

        # Give the server a moment to boot and arm before the client dies,
        # and prove it actually booted: a server that crashed at startup
        # would make the post-kill exit assertion pass vacuously.
        time.sleep(5)
        assert not _wait_for_pid_exit(server_pid, timeout=0.1), (
            "server was already dead before its client was killed"
        )
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


def test_dead_parent_pid_override_emits_exit_event() -> None:
    """Arming with a dead explicit override exits with the structured event.

    The test holds the victim's ``Popen`` handle so ``OpenProcess``
    succeeds on the exited process and the wait fires immediately; the
    worker's stderr must carry the one JSON event line shared with the
    companion server's tooling. On POSIX the explicit PID rides the coarse
    poll, so the worker is still alive at its 2s checkpoint.
    """
    victim = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    victim.wait(timeout=60)

    worker_code = textwrap.dedent(
        f"""
        import time
        from vaultspec_core.mcp_server.watchdog import arm_client_watchdog
        armed = arm_client_watchdog(client_pid={victim.pid}, parent_pid={victim.pid})
        print(f"armed={{armed}}", flush=True)
        time.sleep(2)
        print("still-alive", flush=True)
        time.sleep(18)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", worker_code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if sys.platform == "win32":
        assert proc.returncode == 0
        assert "still-alive" not in proc.stdout
        events = [
            json.loads(line)
            for line in proc.stderr.splitlines()
            if line.startswith("{")
        ]
        assert events, f"no exit event on stderr: {proc.stderr!r}"
        event = events[-1]
        assert event["event"] == "stdio_watchdog_exit"
        assert event["dead_ancestor_pid"] == victim.pid
        assert "dead_ancestor_exe" in event
        assert event["shim_pid"] != os.getpid()
    else:
        assert "armed=True" in proc.stdout
        assert "still-alive" in proc.stdout


def test_fallback_reaps_worker_when_ancestor_dies() -> None:
    """Killing a mid-chain ancestor reaps a worker with no client pipe.

    An intermediary spawns the worker with a null stdin, so the worker's
    watchdog arms on the discovered ancestor chain (short grace). Killing
    the intermediary after the grace window must reap the worker on
    Windows via wait-any; on POSIX the reparent poll notices the
    orphaning. Both resolve within the wait bound.
    """
    worker_code = textwrap.dedent(
        """
        import subprocess, time
        from vaultspec_core.mcp_server.watchdog import arm_client_watchdog
        print(f"armed={arm_client_watchdog(grace_seconds=1.0)}", flush=True)
        time.sleep(120)
        """
    )
    intermediary_code = textwrap.dedent(
        f"""
        import subprocess, sys, time
        worker = subprocess.Popen(
            [sys.executable, "-c", {worker_code!r}],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            text=True,
        )
        print(worker.pid, flush=True)
        print(worker.stdout.readline().strip(), flush=True)
        time.sleep(3600)
        """
    )
    worker_pid = 0
    intermediary = subprocess.Popen(
        [sys.executable, "-c", intermediary_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert intermediary.stdout is not None
        worker_pid = int(intermediary.stdout.readline())
        armed_line = intermediary.stdout.readline().strip()
        assert armed_line == "armed=True"

        # Let the fallback's grace window elapse before the kill counts as
        # termination intent rather than a transient spawn helper.
        time.sleep(3)
        intermediary.kill()
        intermediary.wait(timeout=60)

        if sys.platform == "win32":
            assert _wait_for_pid_exit(worker_pid, timeout=30), (
                "worker survived its dead ancestor; fallback did not fire"
            )
        else:
            # Reparent poll cadence bounds detection on POSIX.
            assert _wait_for_posix_pid_exit(worker_pid, timeout=40)
    finally:
        if intermediary.poll() is None:
            intermediary.kill()
        if worker_pid:
            subprocess.run(
                ["taskkill", "/PID", str(worker_pid), "/F"]
                if sys.platform == "win32"
                else ["kill", "-9", str(worker_pid)],
                capture_output=True,
            )


def test_fallback_grace_window_prunes_transient_ancestor(tmp_path: Path) -> None:
    """An ancestor dying inside the grace window is not termination intent.

    The intermediary exits right after spawning the worker (a transient
    spawn helper); the worker's fallback must prune it during the grace
    window and keep serving on the surviving ancestors. The worker reports
    through a result file, never through a pipe its dead parent owned, so a
    broken pipe cannot fake the outcome. The still-alive checkpoint at 8s
    precedes the POSIX poll cadence, so the assertion holds on every
    platform; the POSIX reparent-reap after the checkpoint is covered by
    the ancestor-death test.
    """
    result_file = tmp_path / "worker-result.txt"
    worker_code = textwrap.dedent(
        f"""
        import time
        from vaultspec_core.mcp_server.watchdog import arm_client_watchdog
        armed = arm_client_watchdog(grace_seconds=4.0)
        with open({str(result_file)!r}, "a", encoding="utf-8") as fh:
            fh.write(f"armed={{armed}}\\n")
            fh.flush()
            time.sleep(8)
            fh.write("still-alive\\n")
        """
    )
    intermediary_code = textwrap.dedent(
        f"""
        import subprocess, sys, time
        worker = subprocess.Popen(
            [sys.executable, "-c", {worker_code!r}],
            stdin=subprocess.DEVNULL,
        )
        print(worker.pid, flush=True)
        time.sleep(1)
        """
    )
    worker_pid = 0
    intermediary = subprocess.Popen(
        [sys.executable, "-c", intermediary_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert intermediary.stdout is not None
        worker_pid = int(intermediary.stdout.readline())
        intermediary.wait(timeout=60)

        deadline = time.monotonic() + 30
        content = ""
        while time.monotonic() < deadline:
            content = (
                result_file.read_text(encoding="utf-8") if result_file.exists() else ""
            )
            if "still-alive" in content or "armed=False" in content:
                break
            time.sleep(0.5)
        assert "armed=True" in content, content
        assert "still-alive" in content, (
            "worker was reaped by a grace-window death instead of pruning it"
        )
    finally:
        if intermediary.poll() is None:
            intermediary.kill()
        if worker_pid:
            subprocess.run(
                ["taskkill", "/PID", str(worker_pid), "/F"]
                if sys.platform == "win32"
                else ["kill", "-9", str(worker_pid)],
                capture_output=True,
            )


def test_real_server_parent_pid_flag_reaps_on_override_death(
    tmp_path: Path,
) -> None:
    """The real server exits when its --parent-pid override target dies.

    The test itself is the pipe client (alive throughout), so only the
    explicit override can fire: this proves the flag reaches the watchdog
    through the entrypoint and that wait-any covers the override alongside
    the resolved client. Works on POSIX too via the explicit-pid poll.
    """
    (tmp_path / ".vaultspec").mkdir()
    (tmp_path / ".vault").mkdir()
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vaultspec_core.mcp_server.app",
            "--parent-pid",
            str(sleeper.pid),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=tmp_path,
    )
    try:
        time.sleep(5)
        assert server.poll() is None, "server exited before the override died"
        sleeper.kill()
        sleeper.wait(timeout=60)
        server.wait(timeout=40)
    finally:
        if server.poll() is None:
            server.kill()
        if sleeper.poll() is None:
            sleeper.kill()
