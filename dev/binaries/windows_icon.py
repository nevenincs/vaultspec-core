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
RT_VERSION = 16
PRIMARY_ICON_GROUP = 1
VERSION_RESOURCE_ID = 1
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


@dataclass(frozen=True)
class VersionInfo:
    """The user-visible string fields carried by a Windows PE version resource."""

    file_version: str
    product_version: str
    product_name: str
    file_description: str
    original_filename: str
    company_name: str
    legal_copyright: str


class VersionResourceError(RuntimeError):
    """A PE version resource is invalid or could not be stamped exactly."""


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


def _pad(data: bytearray) -> None:
    """Pad a version-resource block to the DWORD boundary Win32 requires."""
    data.extend(b"\x00" * (-len(data) % 4))


def _utf16(value: str) -> bytes:
    """Encode a NUL-terminated UTF-16LE resource string."""
    return value.encode("utf-16le") + b"\x00\x00"


def _version_block(
    key: str,
    value: bytes,
    value_length: int,
    value_type: int,
    children: tuple[bytes, ...] = (),
) -> bytes:
    """Build one aligned VERSIONINFO block."""
    data = bytearray(struct.pack("<HHH", 0, value_length, value_type))
    data.extend(_utf16(key))
    _pad(data)
    data.extend(value)
    _pad(data)
    for child in children:
        data.extend(child)
        _pad(data)
    struct.pack_into("<H", data, 0, len(data))
    return bytes(data)


def _version_parts(version: str) -> tuple[int, int, int, int]:
    """Return a four-word VERSIONINFO version tuple."""
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or not all(part.isdigit() for part in parts):
        raise VersionResourceError(f"invalid Windows file version: {version!r}")
    numbers = tuple(int(part) for part in parts)
    if any(number > 0xFFFF for number in numbers):
        raise VersionResourceError(
            f"Windows file version word is too large: {version!r}"
        )
    padded = (*numbers, *(0 for _ in range(4 - len(numbers))))
    return padded[0], padded[1], padded[2], padded[3]


def _fixed_version(value: tuple[int, int, int, int]) -> int:
    """Pack the first two words of a four-part version into one DWORD."""
    return value[0] << 16 | value[1]


def version_resource(info: VersionInfo) -> bytes:
    """Build a Windows VERSIONINFO resource for *info*."""
    file_version = _version_parts(info.file_version)
    product_version = _version_parts(info.product_version)
    fixed = struct.pack(
        "<13I",
        0xFEEF04BD,
        0x00010000,
        _fixed_version(file_version),
        file_version[2] << 16 | file_version[3],
        _fixed_version(product_version),
        product_version[2] << 16 | product_version[3],
        0x3F,
        0,
        0x00000004,
        1,
        0,
        0,
        0,
    )
    strings = tuple(
        _version_block(
            key,
            _utf16(value),
            len(value) + 1,
            1,
        )
        for key, value in (
            ("CompanyName", info.company_name),
            ("FileDescription", info.file_description),
            ("FileVersion", info.file_version),
            ("InternalName", info.original_filename),
            ("OriginalFilename", info.original_filename),
            ("ProductName", info.product_name),
            ("ProductVersion", info.product_version),
            ("LegalCopyright", info.legal_copyright),
        )
    )
    table = _version_block("040904B0", b"", 0, 1, strings)
    string_file_info = _version_block("StringFileInfo", b"", 0, 1, (table,))
    translation = _version_block(
        "Translation",
        struct.pack("<HH", 0x0409, 1200),
        2,
        0,
    )
    var_file_info = _version_block("VarFileInfo", b"", 0, 1, (translation,))
    return _version_block(
        "VS_VERSION_INFO",
        fixed,
        len(fixed),
        0,
        (string_file_info, var_file_info),
    )


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


def stamp_version_info(executable: Path, info: VersionInfo) -> None:
    """Replace the primary PE version resource with *info* and verify it."""
    if not executable.is_file():
        raise VersionResourceError(f"Windows executable does not exist: {executable}")
    payload = version_resource(info)
    kernel32 = _kernel32()
    handle = kernel32.BeginUpdateResourceW(os.fspath(executable), False)
    if not handle:
        _raise_win32("opening resources in", executable)
    committed = False
    try:
        _update_resource(
            kernel32,
            handle,
            RT_VERSION,
            VERSION_RESOURCE_ID,
            payload,
            executable,
        )
        if not kernel32.EndUpdateResourceW(handle, False):
            _raise_win32("committing resources in", executable)
        committed = True
    finally:
        if not committed:
            kernel32.EndUpdateResourceW(handle, True)
    verify_version_info(executable, info)


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


def verify_version_info(executable: Path, info: VersionInfo) -> None:
    """Require the primary PE version resource to match *info* exactly."""
    expected = version_resource(info)
    kernel32 = _kernel32()
    module = kernel32.LoadLibraryExW(
        os.fspath(executable),
        None,
        LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE,
    )
    if not module:
        _raise_win32("loading resources from", executable)
    try:
        actual = _read_resource(
            kernel32, module, RT_VERSION, VERSION_RESOURCE_ID, executable
        )
        if actual != expected:
            raise VersionResourceError(
                f"version resource in {executable} does not match expected metadata"
            )
    finally:
        kernel32.FreeLibrary(module)
