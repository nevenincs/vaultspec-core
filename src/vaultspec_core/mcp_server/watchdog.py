"""Client-process lifetime watchdog for the stdio MCP server.

The stdio transport's lifetime contract is "exit on stdin EOF", but on
Windows inherited pipe handles can keep the stdin pipe open after the
spawning client is gone, so EOF never arrives and the server outlives its
client. This module anchors the server's lifetime to the client process
through layered anchors:

- **Primary (Windows):** resolve the process that created the stdin pipe,
  hold a ``SYNCHRONIZE`` handle to it, and hard-exit the moment it
  terminates - exact-client semantics regardless of wrapper depth.
- **Fallback (Windows):** when stdin is not a client-created pipe, watch
  the discovered ancestor chain instead (handles taken at startup so PID
  reuse cannot retarget the wait, creation-time monotonicity ending the
  walk at a reused PID, and a grace window dropping transient spawn
  helpers).
- **POSIX backstop:** a coarse reparent poll that exits when the server is
  orphaned or an explicitly named client dies; stdin EOF stays the primary
  exit path everywhere.

``VAULTSPEC_STDIO_WATCHDOG`` (``0``/``false``/``off``/``no``) disables all
arming. Every failure path fails open: a watchdog that cannot arm must
never prevent the server from serving. Before every hard exit one
structured JSON event line is flushed to stderr, matching the companion
vaultspec-rag server's event shape so host-side tooling can consume both.

Failing open is bounded on Windows. Losing every anchor - discovery
finding nothing watchable, the grace window pruning the whole chain, or
the wait itself failing - does not disarm the backstop for the process's
lifetime; it enters a re-acquisition poll that re-arms as soon as a live
ancestor is discoverable again. Only after repeated polls positively show
no live ancestor does the server reap itself, because a stdio server no
live process can reach is an orphan and the EOF path is exactly what
cannot recover it there. Two rules keep that poll safe: it never queries
the stdin handle (a named-pipe query blocks behind the transport's
pending read forever), and it decides liveness by process enumeration
rather than ``OpenProcess``, which is refused for higher-integrity
clients that are perfectly alive.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)

#: Operator kill switch; off values disable all arming.
STDIO_WATCHDOG_ENV = "VAULTSPEC_STDIO_WATCHDOG"

_OFF_VALUES = frozenset({"0", "false", "off", "no"})

#: Ancestors beyond this depth are noise (session managers, init); the
#: spawning client is always within a few hops (client -> uv -> launcher).
_MAX_ANCESTOR_DEPTH = 8

#: Seconds before the fallback watchdog arms. Transient spawn helpers
#: (``cmd /c`` wrappers) exit within moments of spawning the chain;
#: discovered ancestors that die during the grace window are dropped
#: instead of treated as termination intent. The precise anchors (resolved
#: client, explicit override) are never grace-pruned.
_GRACE_SECONDS = 10.0

#: Coarse POSIX reparent-poll interval; the backstop does not need to be
#: fast, only eventual.
_POSIX_POLL_SECONDS = 15.0

#: Interval between anchor re-acquisition attempts once every anchor has
#: been lost. The unanchored state is rare, so the poll is coarse: it only
#: has to be eventual.
_REARM_POLL_SECONDS = 30.0

#: Consecutive unanchored polls before the process concludes it is orphaned
#: and reaps itself. A stdio server that can resolve neither a stdin pipe
#: creator nor a single live ancestor for this long has no process left
#: that could be speaking to it.
_ORPHAN_CONFIRMATIONS = 4

_SYNCHRONIZE = 0x0010_0000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x0000_1000
_INFINITE = 0xFFFF_FFFF
_WAIT_OBJECT_0 = 0x0000_0000
_WAIT_TIMEOUT = 0x0000_0102
_TH32CS_SNAPPROCESS = 0x0000_0002


def watchdog_disabled() -> bool:
    """Return whether the operator kill switch disables the watchdog."""
    return os.environ.get(STDIO_WATCHDOG_ENV, "").strip().lower() in _OFF_VALUES


class _WatchedProcess:
    """A process the watchdog holds a ``SYNCHRONIZE`` handle on."""

    __slots__ = ("exe", "grace_prunable", "handle", "pid")

    def __init__(
        self, pid: int, exe: str, handle: int, *, grace_prunable: bool
    ) -> None:
        self.pid = pid
        self.exe = exe
        self.handle = handle
        self.grace_prunable = grace_prunable


def _emit_event(event: str, **fields: object) -> None:
    """Flush one structured JSON event line to stderr.

    The envelope (``event`` plus ``shim_pid``) matches the companion
    vaultspec-rag server's event shape so host tooling parses both from one
    reader, and stderr is used because stdout carries JSON-RPC.
    """
    print(
        json.dumps({"event": event, "shim_pid": os.getpid(), **fields}),
        file=sys.stderr,
        flush=True,
    )


def _exit_on_watched_death(
    pid: int, exe: str, reason: str = "watched_process_exit"
) -> None:
    """Flush one structured event line and hard-exit.

    :func:`os._exit` is deliberate: shutdown must not depend on the event
    loop cooperating mid-teardown, and the blocked stdio reader cannot be
    cancelled in-process. Exit code 0 because self-reaping after the client
    died is the intended outcome, not a crash a supervisor should retry.

    Args:
        pid: The watched process whose death triggered the exit, or ``0``
            when no anchor was ever identified.
        exe: That process's image name.
        reason: Discriminator for hosts consuming the event stream;
            ``watched_process_exit`` for an anchor's death,
            ``unanchored_orphan`` for a confirmed-orphan self-reap.
    """
    _emit_event(
        "stdio_watchdog_exit",
        dead_ancestor_pid=pid,
        dead_ancestor_exe=exe,
        reason=reason,
    )
    os._exit(0)


def _walk_ancestor_pids(
    start_pid: int,
    parents: dict[int, int],
    max_depth: int = _MAX_ANCESTOR_DEPTH,
) -> list[int]:
    """Ancestor PIDs of ``start_pid``, nearest first, bounded and cycle-safe.

    ``parents`` maps pid to parent pid as observed in one snapshot. The walk
    stops at the depth bound, at a missing entry, at pid 0/self-parenting,
    and at any pid already seen (snapshot cycles happen when PIDs were
    reused between rows).
    """
    chain: list[int] = []
    seen: set[int] = {start_pid}
    pid = start_pid
    for _ in range(max_depth):
        ppid = parents.get(pid)
        if ppid is None or ppid == 0 or ppid == pid or ppid in seen:
            break
        chain.append(ppid)
        seen.add(ppid)
        pid = ppid
    return chain


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _PROCESSENTRY32(ctypes.Structure):
        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        )

    class _FILETIME(ctypes.Structure):
        _fields_ = (
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        )

    # Undeclared ctypes signatures marshal through default int inference and
    # fail silently when they drift, so every binding declares argtypes and
    # restype (OpenProcess in particular truncates 64-bit handles without a
    # pointer-sized restype).
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.GetNamedPipeServerProcessId.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.WaitForMultipleObjects.argtypes = (
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.BOOL,
        wintypes.DWORD,
    )
    _kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
    _kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32First.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESSENTRY32),
    )
    _kernel32.Process32First.restype = wintypes.BOOL
    _kernel32.Process32Next.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESSENTRY32),
    )
    _kernel32.Process32Next.restype = wintypes.BOOL
    _kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
    )
    _kernel32.GetProcessTimes.restype = wintypes.BOOL

    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    def _snapshot_processes() -> tuple[dict[int, int], dict[int, str]]:
        """One Toolhelp32 pass: pid to ppid and pid to exe name."""
        snap = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if snap is None or snap == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        parents: dict[int, int] = {}
        names: dict[int, str] = {}
        try:
            entry = _PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
            ok = bool(_kernel32.Process32First(snap, ctypes.byref(entry)))
            while ok:
                pid = int(entry.th32ProcessID)
                parents[pid] = int(entry.th32ParentProcessID)
                names[pid] = entry.szExeFile.decode(errors="replace")
                ok = bool(_kernel32.Process32Next(snap, ctypes.byref(entry)))
        finally:
            _kernel32.CloseHandle(snap)
        return parents, names

    def _creation_time(handle: int) -> int:
        """Process creation time as a FILETIME integer; 0 when unreadable."""
        created = _FILETIME()
        exited = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        ok = _kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not ok:
            return 0
        return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)

    def _open_process(pid: int) -> int | None:
        handle = _kernel32.OpenProcess(
            _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        return int(handle) if handle else None

    def _self_creation_time() -> int:
        """This process's creation time as a FILETIME integer; 0 if unreadable."""
        handle = _open_process(os.getpid())
        if handle is None:
            return 0
        try:
            return _creation_time(handle)
        finally:
            _kernel32.CloseHandle(handle)

    def _predates(handle: int, reference_ctime: int) -> bool:
        """Whether the handle's process is old enough to be a genuine anchor.

        A real ancestor - and the process that created this process's stdin
        pipe - necessarily existed first, so a candidate younger than the
        reference is a reused PID wearing a dead process's number. An
        unreadable reference fails open and accepts the candidate.
        """
        if not reference_ctime:
            return True
        candidate_ctime = _creation_time(handle)
        return candidate_ctime != 0 and candidate_ctime <= reference_ctime

    def _close_targets(targets: list[_WatchedProcess]) -> None:
        """Release every held process handle in *targets*."""
        for target in targets:
            _kernel32.CloseHandle(target.handle)

    def resolve_stdin_client_pid() -> int | None:
        """Resolve the PID of the process that created this process's stdin pipe.

        Anonymous pipes are named pipes under the hood on Windows, so
        ``GetNamedPipeServerProcessId`` on the inherited stdin handle yields
        the pipe-creating process: the MCP client, regardless of how many
        wrapper processes (``uv``, venv launchers) sit in between.

        Returns:
            The client PID, or ``None`` when stdin is not a pipe (console or
            redirected-file stdin), the handle is unavailable, or the
            resolved PID is this process itself. Fails open on anything
            unexpected.
        """
        try:
            import msvcrt

            try:
                handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            except OSError:
                logger.debug("watchdog: no stdin OS handle")
                return None

            server_pid = ctypes.c_ulong(0)
            ok = _kernel32.GetNamedPipeServerProcessId(handle, ctypes.byref(server_pid))
            if not ok:
                logger.debug(
                    "watchdog: stdin is not a pipe (error %d)",
                    ctypes.get_last_error(),
                )
                return None

            pid = int(server_pid.value)
            if pid == 0 or pid == os.getpid():
                logger.debug("watchdog: pipe creator is self or unresolved (%d)", pid)
                return None
            return pid
        except Exception:
            logger.debug("watchdog: client resolution failed", exc_info=True)
            return None

    def _open_ancestor_chain() -> list[_WatchedProcess]:
        """SYNCHRONIZE handles on the live ancestor chain, PID-reuse safe.

        Walks the snapshot parent chain from this process, opening each
        ancestor's handle immediately and enforcing creation-time
        monotonicity: a genuine ancestor existed before its child, so a
        "parent" younger than the child is a reused PID and ends the walk.
        """
        watched: list[_WatchedProcess] = []
        parents, names = _snapshot_processes()
        child_ctime = _self_creation_time()
        for pid in _walk_ancestor_pids(os.getpid(), parents):
            handle = _open_process(pid)
            if handle is None:
                break
            ancestor_ctime = _creation_time(handle)
            if child_ctime and (ancestor_ctime == 0 or ancestor_ctime > child_ctime):
                _kernel32.CloseHandle(handle)
                break
            watched.append(
                _WatchedProcess(pid, names.get(pid, "?"), handle, grace_prunable=True)
            )
            child_ctime = ancestor_ctime
        return watched

    def _open_watched(pid: int, *, grace_prunable: bool) -> _WatchedProcess | None:
        """Open one explicit PID as a watched process; ``None`` when refused."""
        handle = _open_process(pid)
        if handle is None:
            logger.debug(
                "watchdog: cannot open process %d (error %d)",
                pid,
                ctypes.get_last_error(),
            )
            return None
        try:
            _, names = _snapshot_processes()
            exe = names.get(pid, "?")
        except Exception:
            exe = "?"
        return _WatchedProcess(pid, exe, handle, grace_prunable=grace_prunable)

    def _grace_prune(
        watched: list[_WatchedProcess], grace_seconds: float
    ) -> list[_WatchedProcess]:
        """Sleep the grace window and drop discovered ancestors already gone.

        Only discovered-chain targets are grace prunable; the resolved
        client and an explicit override are returned untouched, preserving
        the instant reap of an already-dead client.
        """
        if any(w.grace_prunable for w in watched):
            time.sleep(grace_seconds)
        survivors: list[_WatchedProcess] = []
        for target in watched:
            # Short-circuits: a non-prunable anchor is kept without being
            # probed, so an already-dead client still signals immediately.
            if (
                not target.grace_prunable
                or _kernel32.WaitForSingleObject(target.handle, 0) == _WAIT_TIMEOUT
            ):
                survivors.append(target)
            else:
                _kernel32.CloseHandle(target.handle)
                logger.info(
                    "watchdog: dropping ancestor %d (%s) gone during grace",
                    target.pid,
                    target.exe,
                )
        return survivors

    def _wait_any(targets: list[_WatchedProcess]) -> _WatchedProcess | None:
        """Block until one target exits; ``None`` when the wait itself failed."""
        handles = (wintypes.HANDLE * len(targets))(
            *[target.handle for target in targets]
        )
        result = int(
            _kernel32.WaitForMultipleObjects(len(targets), handles, False, _INFINITE)
        )
        index = result - _WAIT_OBJECT_0
        if not 0 <= index < len(targets):
            logger.warning(
                "watchdog: wait failed (result 0x%x, error %d)",
                result,
                ctypes.get_last_error(),
            )
            return None
        return targets[index]

    def _reacquire_targets() -> list[_WatchedProcess] | None:
        """Anchors visible right now; ``None`` when the observation is ambiguous.

        Two constraints shape this probe, both learned from the companion
        vaultspec-rag server's fix for the same defect:

        It must never touch stdin. :func:`resolve_stdin_client_pid` is safe
        only on the main thread before the transport starts; once the
        reader has a ``ReadFile`` pending on that handle, a named-pipe
        query blocks behind it for the life of the process, turning a
        recoverable disarm into a silent permanent hang.

        Enumeration, not ``OpenProcess``, decides liveness. A Toolhelp
        snapshot lists processes without needing rights on them, while
        ``OpenProcess`` is refused for a higher-integrity target - so a
        live-but-privileged client appears in the snapshot and nowhere
        else, and reaping on the handle walk alone would kill servers whose
        clients are alive.

        Nothing returned is grace prunable: a process still alive this far
        past startup is a genuine anchor, not a transient spawn helper.

        Returns:
            Freshly opened anchors to wait on; an empty list when
            enumeration positively shows no live ancestor; ``None`` when
            the observation cannot be trusted - a failed snapshot, or live
            ancestors that refuse inspection - which must never count
            toward declaring the process orphaned.
        """
        try:
            parents, names = _snapshot_processes()
        except Exception:
            logger.debug("watchdog: process snapshot failed", exc_info=True)
            return None
        # A pid present as a snapshot key is a running process; the walk's
        # chain may end on a recorded ppid whose process is already gone.
        live = [
            pid for pid in _walk_ancestor_pids(os.getpid(), parents) if pid in parents
        ]
        if not live:
            return []
        self_ctime = _self_creation_time()
        targets: list[_WatchedProcess] = []
        for pid in live:
            handle = _open_process(pid)
            if handle is None:
                continue
            if not _predates(handle, self_ctime):
                # A PID that outlived its process and got reused is not an
                # ancestor; waiting on it would reap this server when an
                # unrelated process exits.
                _kernel32.CloseHandle(handle)
                continue
            targets.append(
                _WatchedProcess(pid, names.get(pid, "?"), handle, grace_prunable=False)
            )
        if not targets:
            # Live ancestors exist but none can be watched. Ambiguous, so
            # keep polling rather than reaping a server that still has a
            # client; races may only ever extend protection.
            logger.debug(
                "watchdog: %d live ancestor(s) visible but none watchable", len(live)
            )
            return None
        return targets

    def _windows_wait(
        watched: list[_WatchedProcess],
        grace_seconds: float,
        rearm_seconds: float = _REARM_POLL_SECONDS,
        orphan_confirmations: int = _ORPHAN_CONFIRMATIONS,
    ) -> None:
        """Wait on the anchors, re-acquiring rather than disarming for good.

        Runs on a daemon thread. Discovered ancestors are grace pruned
        first, then the survivors are waited on and any death hard-exits
        the process. Losing every anchor - arming with nothing watchable,
        the grace window pruning the whole chain, or the wait API failing -
        no longer ends the watchdog: it falls into a re-acquisition poll
        that re-arms the moment an anchor resolves again, and reaps the
        process only once ``orphan_confirmations`` consecutive polls agree
        that neither a stdin pipe creator nor one live ancestor exists.
        That state is the orphan stdin EOF cannot recover from on Windows.
        """
        targets = _grace_prune(watched, grace_seconds)
        if not targets:
            _emit_event("stdio_watchdog_disarmed", reason="no_anchor_after_grace")
        unanchored_polls = 0
        while True:
            if targets:
                dead = _wait_any(targets)
                if dead is not None:
                    _exit_on_watched_death(dead.pid, dead.exe)
                # The wait failed on live targets: release the handles and
                # rebuild from discovery instead of leaving the process
                # unanchored for the rest of its life.
                _close_targets(targets)
                targets = []
                unanchored_polls = 0
                _emit_event("stdio_watchdog_disarmed", reason="wait_failed")
            time.sleep(rearm_seconds)
            reacquired = _reacquire_targets()
            if reacquired is None:
                # Ambiguous observation: reset rather than accumulate, so a
                # race can only ever extend protection.
                unanchored_polls = 0
                continue
            if reacquired:
                targets = reacquired
                unanchored_polls = 0
                logger.info(
                    "watchdog: re-armed on %s",
                    ", ".join(f"{t.pid}({t.exe})" for t in targets),
                )
                continue
            unanchored_polls += 1
            logger.warning(
                "watchdog: no anchor resolvable (%d/%d confirmations)",
                unanchored_polls,
                orphan_confirmations,
            )
            if unanchored_polls >= orphan_confirmations:
                _exit_on_watched_death(0, "<unanchored>", reason="unanchored_orphan")

else:

    def resolve_stdin_client_pid() -> int | None:
        """POSIX has no pipe-creator resolution; the reparent poll covers it."""
        return None


def _pid_alive(pid: int) -> bool:
    """POSIX liveness probe (never use ``os.kill(pid, 0)`` on Windows)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        logger.debug("watchdog: liveness probe failed for pid %d", pid, exc_info=True)
        return True
    return True


def _posix_watchdog(initial_ppid: int, extra_pids: tuple[int, ...]) -> None:
    """Coarse reparent poll: exit when orphaned or an explicit client dies."""
    while True:
        time.sleep(_POSIX_POLL_SECONDS)
        ppid = os.getppid()
        if ppid != initial_ppid:
            _exit_on_watched_death(initial_ppid, "parent")
        for pid in extra_pids:
            if not _pid_alive(pid):
                _exit_on_watched_death(pid, "explicit-client")


def arm_client_watchdog(
    client_pid: int | None = None,
    parent_pid: int | None = None,
    grace_seconds: float = _GRACE_SECONDS,
    rearm_seconds: float = _REARM_POLL_SECONDS,
    orphan_confirmations: int = _ORPHAN_CONFIRMATIONS,
) -> bool:
    """Arm the lifetime backstop; return whether a watchdog thread started.

    On Windows the primary anchor is the stdin pipe creator resolved by
    :func:`resolve_stdin_client_pid` (or the injected ``client_pid``); when
    resolution declines, the discovered ancestor chain is watched instead,
    grace-pruned so transient spawn helpers do not count as termination
    intent. An explicit ``parent_pid`` (the ``--parent-pid`` entrypoint
    override) is watched ahead of discovery in either mode. Finding nothing
    watchable still arms: the thread polls for an anchor and self-reaps only
    on confirmed orphanhood. On POSIX a coarse reparent poll backstops
    abandonment without pipe closure.

    Arming failures fail open, and ``VAULTSPEC_STDIO_WATCHDOG`` off values
    skip arming entirely.

    Args:
        client_pid: Explicit client PID for the primary anchor. Defaults to
            the stdin pipe creator.
        parent_pid: Additional process to watch ahead of discovery.
        grace_seconds: Fallback grace window before discovered ancestors
            count as termination intent.
        rearm_seconds: Windows only; interval between anchor re-acquisition
            attempts while no anchor is held.
        orphan_confirmations: Windows only; consecutive unanchored polls
            required before the process reaps itself as an orphan.

    Returns:
        ``True`` when a watchdog thread armed, ``False`` when arming was
        disabled or failed open and the server retains EOF-only shutdown.
    """
    if watchdog_disabled():
        logger.info(
            "watchdog: disabled via %s; stdin EOF is the only exit path",
            STDIO_WATCHDOG_ENV,
        )
        return False

    try:
        if sys.platform == "win32":
            watched: list[_WatchedProcess] = []
            if parent_pid is not None:
                explicit = _open_watched(parent_pid, grace_prunable=False)
                if explicit is None:
                    logger.warning(
                        "watchdog: explicit parent pid %d not watchable", parent_pid
                    )
                else:
                    watched.append(explicit)
            resolved = client_pid or resolve_stdin_client_pid()
            client_watched = False
            if resolved is not None:
                if any(w.pid == resolved for w in watched):
                    client_watched = True
                else:
                    client = _open_watched(resolved, grace_prunable=False)
                    if client is not None:
                        watched.append(client)
                        client_watched = True
            if not client_watched:
                fallback = _open_ancestor_chain()
                known = {w.pid for w in watched}
                for target in fallback:
                    if target.pid in known:
                        # Already watched (an explicit override on the
                        # chain); drop the duplicate without leaking its
                        # freshly opened handle.
                        _kernel32.CloseHandle(target.handle)
                    else:
                        watched.append(target)
            if not watched:
                # Nothing watchable is the orphan signature itself, not a
                # reason to stand down: arm on an empty set so the thread
                # polls for an anchor and reaps on confirmed orphanhood.
                logger.debug(
                    "watchdog: no watchable targets; "
                    "arming the unanchored re-acquisition poll"
                )
            thread = threading.Thread(
                target=_windows_wait,
                args=(watched, grace_seconds, rearm_seconds, orphan_confirmations),
                name="mcp-client-watchdog",
                daemon=True,
            )
            try:
                thread.start()
            except Exception:
                _close_targets(watched)
                raise
            logger.debug(
                "watchdog: armed on %s",
                ", ".join(f"{w.pid}({w.exe})" for w in watched) or "no anchor yet",
            )
            return True

        extra = (parent_pid,) if parent_pid is not None else ()
        thread = threading.Thread(
            target=_posix_watchdog,
            args=(os.getppid(), extra),
            name="mcp-client-watchdog",
            daemon=True,
        )
        thread.start()
        logger.debug("watchdog: armed POSIX reparent poll")
        return True
    except Exception:
        logger.debug("watchdog: arming failed; not arming", exc_info=True)
        return False
