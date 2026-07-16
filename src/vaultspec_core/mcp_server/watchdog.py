"""Windows client-process watchdog for the stdio MCP server.

The stdio transport's lifetime contract is "exit on stdin EOF", but on
Windows inherited pipe handles can keep the stdin pipe open after the
spawning client is gone, so EOF never arrives and the server outlives its
client. This module anchors the server's lifetime to the client process
itself: it resolves the process that created the stdin pipe, holds a
``SYNCHRONIZE`` handle to it, and hard-exits the server the moment that
process terminates.

Every failure path fails open: when the watchdog cannot arm (non-Windows
platform, console stdin, inaccessible client process), the server keeps the
plain EOF-only behavior.
"""

from __future__ import annotations

import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

_SYNCHRONIZE = 0x0010_0000
_INFINITE = 0xFFFF_FFFF
_WAIT_OBJECT_0 = 0x0000_0000


def _kernel32():  # pragma: no cover - trivial loader, Windows-only
    """Load ``kernel32`` with last-error capture and correct prototypes.

    ``OpenProcess`` needs an explicit ``c_void_p`` restype: the ctypes
    default of ``c_int`` truncates 64-bit handle values.

    Returns:
        The configured :class:`ctypes.WinDLL` instance.
    """
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    return kernel32


def resolve_stdin_client_pid() -> int | None:
    """Resolve the PID of the process that created this process's stdin pipe.

    Anonymous pipes are named pipes under the hood on Windows, so
    ``GetNamedPipeServerProcessId`` on the inherited stdin handle yields the
    pipe-creating process: the MCP client, regardless of how many wrapper
    processes (``uv``, venv launchers) sit in between.

    Returns:
        The client PID, or ``None`` when stdin is not a pipe (console or
        redirected-file stdin), the handle is unavailable, or the resolved
        PID is this process itself.
    """
    if sys.platform != "win32":
        return None

    import ctypes
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    except OSError:
        logger.debug("watchdog: no stdin OS handle; not arming")
        return None

    kernel32 = _kernel32()
    server_pid = ctypes.c_ulong(0)
    ok = kernel32.GetNamedPipeServerProcessId(
        ctypes.c_void_p(handle), ctypes.byref(server_pid)
    )
    if not ok:
        logger.debug(
            "watchdog: stdin is not a pipe (error %d); not arming",
            ctypes.get_last_error(),
        )
        return None

    pid = int(server_pid.value)
    if pid == 0 or pid == os.getpid():
        logger.debug(
            "watchdog: pipe creator is self or unresolved (%d); not arming", pid
        )
        return None
    return pid


def arm_client_watchdog(client_pid: int | None = None) -> bool:
    """Arm a daemon thread that exits the server when the client process dies.

    Opens the client process with ``SYNCHRONIZE`` access and blocks on
    ``WaitForSingleObject`` in a daemon thread. When the client's process
    handle signals, the thread calls :func:`os._exit` so shutdown does not
    depend on the event loop cooperating mid-teardown; the wrapper chain
    above the worker unwinds on its own once the worker exits.

    Args:
        client_pid: Explicit client PID to watch. Defaults to the stdin
            pipe creator resolved by :func:`resolve_stdin_client_pid`.

    Returns:
        ``True`` when the watchdog armed, ``False`` when it failed open and
        the server retains EOF-only shutdown.
    """
    if sys.platform != "win32":
        return False
    if client_pid is None:
        client_pid = resolve_stdin_client_pid()
    if client_pid is None:
        return False

    import ctypes

    kernel32 = _kernel32()
    process_handle = kernel32.OpenProcess(
        _SYNCHRONIZE, False, ctypes.c_ulong(client_pid)
    )
    if not process_handle:
        logger.debug(
            "watchdog: cannot open client process %d (error %d); not arming",
            client_pid,
            ctypes.get_last_error(),
        )
        return False

    def _wait_for_client_exit() -> None:
        result = kernel32.WaitForSingleObject(
            ctypes.c_void_p(process_handle), _INFINITE
        )
        if result == _WAIT_OBJECT_0:
            logger.info("watchdog: client process %d exited; shutting down", client_pid)
            os._exit(0)
        logger.debug(
            "watchdog: wait on client process %d ended without exit signal (result %d)",
            client_pid,
            result,
        )

    threading.Thread(
        target=_wait_for_client_exit,
        name="mcp-client-watchdog",
        daemon=True,
    ).start()
    logger.debug("watchdog: armed on client process %d", client_pid)
    return True
