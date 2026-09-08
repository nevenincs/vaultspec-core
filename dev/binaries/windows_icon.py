"""Stamp and verify the application icon in Windows PE executables.

The release builder runs from a bare standard-library Python environment, so
resource updates use the Win32 API directly instead of a packaging dependency.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import struct
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

RT_ICON = 3
RT_GROUP_ICON = 14
PRIMARY_ICON_GROUP = 1
LANG_NEUTRAL = 0
LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020


class IconResourceError(RuntimeError):
    """An ICO is invalid or a PE icon could not be stamped exactly."""


@dataclass(frozen=True)
class IconImage:
    """One decoded ICO directory entry and its image payload."""

    width: int
    height: int
    colors: int
    planes: int
    bit_count: int
    payload: bytes


def parse_ico(path: Path) -> tuple[IconImage, ...]:
    """Parse *path* as a bounded ICO container and return all image frames."""
    blob = path.read_bytes()
    if len(blob) < 6:
        raise IconResourceError(f"{path} is shorter than an ICO header")
    reserved, kind, count = struct.unpack_from("<HHH", blob)
    if reserved != 0 or kind != 1 or count == 0:
        raise IconResourceError(
            f"{path} has invalid ICO header values ({reserved}, {kind}, {count})"
        )
    directory_end = 6 + count * 16
    if directory_end > len(blob):
        raise IconResourceError(f"{path} has a truncated ICO directory")

    images: list[IconImage] = []
    spans: list[tuple[int, int]] = []
    for index in range(count):
        entry = 6 + index * 16
        width, height, colors, entry_reserved, planes, bits, size, offset = (
            struct.unpack_from("<BBBBHHII", blob, entry)
        )
        end = offset + size
        if (
            entry_reserved != 0
            or size == 0
            or offset < directory_end
            or end > len(blob)
        ):
            raise IconResourceError(f"{path} has invalid ICO frame {index}")
        if any(
            offset < prior_end and prior_start < end for prior_start, prior_end in spans
        ):
            raise IconResourceError(f"{path} has overlapping ICO frame data")
        spans.append((offset, end))
        images.append(
            IconImage(
                width=width or 256,
                height=height or 256,
                colors=colors,
                planes=planes,
                bit_count=bits,
                payload=blob[offset:end],
            )
        )
    return tuple(images)


def _resource_id(value: int) -> ctypes.c_void_p:
    """Return the integer-resource pointer representation Win32 expects."""
    return ctypes.c_void_p(value)


def _kernel32() -> Any:
    """Load kernel32 with last-error capture, or reject a non-Windows host."""
    if sys.platform != "win32":
        raise IconResourceError("Windows PE resources can only be updated on Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.BeginUpdateResourceW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.BOOL,
    ]
    kernel32.BeginUpdateResourceW.restype = ctypes.wintypes.HANDLE
    kernel32.UpdateResourceW.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.wintypes.WORD,
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.DWORD,
    ]
    kernel32.UpdateResourceW.restype = ctypes.wintypes.BOOL
    kernel32.EndUpdateResourceW.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.BOOL,
    ]
    kernel32.EndUpdateResourceW.restype = ctypes.wintypes.BOOL
    kernel32.LoadLibraryExW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
    ]
    kernel32.LoadLibraryExW.restype = ctypes.wintypes.HMODULE
    kernel32.FindResourceW.argtypes = [
        ctypes.wintypes.HMODULE,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.FindResourceW.restype = ctypes.wintypes.HRSRC
    kernel32.SizeofResource.argtypes = [ctypes.wintypes.HMODULE, ctypes.wintypes.HRSRC]
    kernel32.SizeofResource.restype = ctypes.wintypes.DWORD
    kernel32.LoadResource.argtypes = [ctypes.wintypes.HMODULE, ctypes.wintypes.HRSRC]
    kernel32.LoadResource.restype = ctypes.wintypes.HGLOBAL
    kernel32.LockResource.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.LockResource.restype = ctypes.wintypes.LPVOID
    kernel32.FreeLibrary.argtypes = [ctypes.wintypes.HMODULE]
    kernel32.FreeLibrary.restype = ctypes.wintypes.BOOL
    return kernel32


def _raise_win32(action: str, path: Path) -> None:
    windows_ctypes = cast("Any", ctypes)
    code = windows_ctypes.get_last_error()
    detail = windows_ctypes.FormatError(code).strip()
    raise IconResourceError(f"{action} {path} failed: [{code}] {detail}")


def _group_data(images: tuple[IconImage, ...]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b"".join(
        struct.pack(
            "<BBBBHHIH",
            image.width if image.width < 256 else 0,
            image.height if image.height < 256 else 0,
            image.colors,
            0,
            image.planes,
            image.bit_count,
            len(image.payload),
            resource_id,
        )
        for resource_id, image in enumerate(images, start=1)
    )
    return header + entries


def _update_resource(
    kernel32: Any,
    handle: int,
    kind: int,
    resource_id: int,
    payload: bytes,
    executable: Path,
) -> None:
    buffer = ctypes.create_string_buffer(payload)
    updated = kernel32.UpdateResourceW(
        handle,
        _resource_id(kind),
        _resource_id(resource_id),
        LANG_NEUTRAL,
        ctypes.cast(buffer, ctypes.wintypes.LPVOID),
        len(payload),
    )
    if not updated:
        _raise_win32(f"updating resource {kind}/{resource_id} in", executable)


def stamp_icon(executable: Path, icon: Path) -> None:
    """Replace the primary PE icon with *icon* and verify the committed bytes."""
    if not executable.is_file():
        raise IconResourceError(f"Windows executable does not exist: {executable}")
    images = parse_ico(icon)
    kernel32 = _kernel32()
    handle = kernel32.BeginUpdateResourceW(os.fspath(executable), False)
    if not handle:
        _raise_win32("opening resources in", executable)
    committed = False
    try:
        for resource_id, image in enumerate(images, start=1):
            _update_resource(
                kernel32, handle, RT_ICON, resource_id, image.payload, executable
            )
        _update_resource(
            kernel32,
            handle,
            RT_GROUP_ICON,
            PRIMARY_ICON_GROUP,
            _group_data(images),
            executable,
        )
        if not kernel32.EndUpdateResourceW(handle, False):
            _raise_win32("committing resources in", executable)
        committed = True
    finally:
        if not committed:
            kernel32.EndUpdateResourceW(handle, True)
    verify_icon(executable, icon)


def _read_resource(
    kernel32: Any, module: int, kind: int, resource_id: int, executable: Path
) -> bytes:
    resource = kernel32.FindResourceW(
        module, _resource_id(resource_id), _resource_id(kind)
    )
    if not resource:
        _raise_win32(f"finding resource {kind}/{resource_id} in", executable)
    size = kernel32.SizeofResource(module, resource)
    loaded = kernel32.LoadResource(module, resource)
    address = kernel32.LockResource(loaded)
    if not size or not loaded or not address:
        _raise_win32(f"reading resource {kind}/{resource_id} from", executable)
    return ctypes.string_at(address, size)


def verify_icon(executable: Path, icon: Path) -> None:
    """Require the PE's primary icon group to match *icon* exactly."""
    images = parse_ico(icon)
    expected_group = _group_data(images)
    kernel32 = _kernel32()
    module = kernel32.LoadLibraryExW(
        os.fspath(executable),
        None,
        LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE,
    )
    if not module:
        _raise_win32("loading resources from", executable)
    try:
        actual_group = _read_resource(
            kernel32, module, RT_GROUP_ICON, PRIMARY_ICON_GROUP, executable
        )
        if actual_group != expected_group:
            raise IconResourceError(
                f"primary icon group in {executable} does not match {icon}"
            )
        for resource_id, image in enumerate(images, start=1):
            actual = _read_resource(kernel32, module, RT_ICON, resource_id, executable)
            if actual != image.payload:
                raise IconResourceError(
                    f"icon frame {resource_id} in {executable} does not match {icon}"
                )
    finally:
        kernel32.FreeLibrary(module)
