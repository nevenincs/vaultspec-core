"""Resolve an already-open Windows file without opening it again by pathname."""

from __future__ import annotations

import ctypes
import os
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable


@cache
def _final_path_function() -> Callable[
    [int, ctypes.Array[ctypes.c_wchar], int, int], int
]:
    from ctypes import wintypes

    function = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
    function.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    function.restype = wintypes.DWORD
    return cast(
        "Callable[[int, ctypes.Array[ctypes.c_wchar], int, int], int]", function
    )


def _handle_path(handle: int) -> Path:
    """Read a normalized DOS/UNC path from a borrowed Win32 handle."""
    function = _final_path_function()
    for capacity in (512, 32768):
        buffer = ctypes.create_unicode_buffer(capacity)
        length = function(handle, buffer, capacity, 0)
        if length == 0:
            raise ctypes.WinError(ctypes.get_last_error())
        if length < capacity:
            return normalise_path(buffer.value)
    raise OSError("Opened file path exceeds the Windows path limit")


def normalise_path(value: str) -> Path:
    """Use one DOS/UNC spelling for both pinned roots and opened file paths."""
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def opened_file_path(descriptor: int) -> Path:
    """Resolve the file already owned by this CRT descriptor, without reopening."""
    import msvcrt

    return _handle_path(msvcrt.get_osfhandle(descriptor))


@cache
def _file_functions() -> tuple[Any, Any]:
    """Bind the Win32 foreign-function boundary once."""
    from ctypes import wintypes

    library = ctypes.WinDLL("kernel32", use_last_error=True)
    create = library.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    close = library.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    return create, close


def open_file_nofollow(path: Path) -> int:
    """Open existing bytes read-only without following a final reparse point.

    Share reads and writes, as the CRT reader does, but not deletion. The caller
    owns the resulting descriptor and must verify type, identity, and rooted path.
    """
    import msvcrt

    create, close = _file_functions()
    # GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, OPEN_EXISTING,
    # FILE_FLAG_OPEN_REPARSE_POINT. The OS's normal read cache remains enabled.
    handle = cast("int", create(str(path), 0x80000000, 3, None, 3, 0x00200000, None))
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
    except BaseException:
        close(handle)
        raise


def resolved_path(path: Path) -> Path:
    """Resolve one file or directory through a single metadata-only handle.

    The caller compares this canonical spelling against its pinned root. Unlike
    Path.resolve(), no second open verifies a prefix-stripped spelling which
    the caller will reject if it differs from the required rooted spelling.
    """
    create, close = _file_functions()
    # No data access; share read/write/delete; allow directory handles.
    handle = cast("int", create(str(path), 0, 7, None, 3, 0x02000000, None))
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _handle_path(handle)
    finally:
        close(handle)
