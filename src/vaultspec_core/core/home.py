"""Canonical machine-global VaultSpec home layout and process-registry probes."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

VAULTSPEC_HOME_DIRNAME = ".vaultspec"
PROCS_DIRNAME = "procs"
LEASES_DIRNAME = "leases"


class ProcessRegistrySignal(StrEnum):
    """Observed state of the optional machine-global process registry."""

    ABSENT = "absent"
    HEALTHY = "healthy"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class CoreHomeLayout:
    """Paths reserved by Core below one machine-global home."""

    root: Path
    procs: Path
    leases: Path


@dataclass(frozen=True, slots=True)
class ProcessRegistryDiagnosis:
    """Non-destructive liveness summary for ``procs/*.json`` records."""

    signal: ProcessRegistrySignal
    record_count: int = 0
    stale_records: tuple[str, ...] = ()


def core_home_layout(home: Path | None = None) -> CoreHomeLayout:
    """Resolve Core's machine-global home and its reserved process paths.

    ``home`` names the Core home itself.  The explicit form exists for callers
    and real-filesystem tests that must not depend on the operator's account.
    """
    root = home if home is not None else Path.home() / VAULTSPEC_HOME_DIRNAME
    procs = root / PROCS_DIRNAME
    return CoreHomeLayout(root=root, procs=procs, leases=procs / LEASES_DIRNAME)


def _record_pid(path: Path) -> int | None:
    """Read only the interoperable ``pid`` field from one registry record."""
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return None
    if not isinstance(value, dict):
        return None
    pid = cast("dict[str, object]", value).get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    return pid


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _SYNCHRONIZE = 0x0010_0000
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 0x0000_0102
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL

    def _pid_is_alive(pid: int) -> bool:
        handle = _kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER is the documented no-such-process result.
            # Access-denied and other inconclusive failures must fail open: a
            # higher-integrity live process is not a stale record.
            return ctypes.get_last_error() != 87
        try:
            wait_result = _kernel32.WaitForSingleObject(handle, 0)
            # WAIT_TIMEOUT proves liveness. WAIT_FAILED and unexpected results
            # are inconclusive, so they also fail open rather than invent death.
            return wait_result != _WAIT_OBJECT_0
        finally:
            _kernel32.CloseHandle(handle)

else:

    def _pid_is_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        return True


def diagnose_process_registry(home: Path | None = None) -> ProcessRegistryDiagnosis:
    """Inspect process-record PID liveness without mutating the Core home.

    Record payloads remain owned by their producing tool.  Core deliberately
    reads only a positive integer ``pid`` and ignores unknown, malformed, and
    nested artifacts so schema evolution and ``procs/leases/`` stay opaque.
    """
    procs = core_home_layout(home).procs
    if not procs.is_dir():
        return ProcessRegistryDiagnosis(ProcessRegistrySignal.ABSENT)

    records: list[str] = []
    stale: list[str] = []
    for path in sorted(procs.glob("*.json")):
        pid = _record_pid(path)
        if pid is None:
            continue
        records.append(path.name)
        if not _pid_is_alive(pid):
            stale.append(path.name)

    signal = ProcessRegistrySignal.STALE if stale else ProcessRegistrySignal.HEALTHY
    return ProcessRegistryDiagnosis(signal, len(records), tuple(stale))


__all__ = [
    "CoreHomeLayout",
    "ProcessRegistryDiagnosis",
    "ProcessRegistrySignal",
    "core_home_layout",
    "diagnose_process_registry",
]
