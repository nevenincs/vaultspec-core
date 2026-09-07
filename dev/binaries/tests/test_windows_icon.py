"""Exact ICO parsing and Windows PE resource tests."""

from __future__ import annotations

import hashlib
import shutil
import struct
import sys
from typing import TYPE_CHECKING

import pytest

from dev.binaries.build_pyapp import APPLICATION_ICON, publish_asset
from dev.binaries.windows_icon import (
    IconResourceError,
    parse_ico,
    verify_icon,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

EXPECTED_SIZES = (16, 32, 48, 64, 128, 256)


def test_governed_icon_contains_the_exact_frame_inventory() -> None:
    """The committed ICO is a real ordered multi-frame application icon."""
    images = parse_ico(APPLICATION_ICON)

    assert tuple(sorted(image.width for image in images)) == EXPECTED_SIZES
    assert tuple(sorted(image.height for image in images)) == EXPECTED_SIZES
    assert all(image.payload for image in images)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        struct.pack("<HHH", 1, 1, 1),
        struct.pack("<HHH", 0, 2, 1),
        struct.pack("<HHH", 0, 1, 0),
        struct.pack("<HHH", 0, 1, 1),
        struct.pack("<HHHBBBBHHII", 0, 1, 1, 16, 16, 0, 0, 1, 32, 99, 22),
    ],
)
def test_parse_ico_rejects_malformed_containers(tmp_path: Path, payload: bytes) -> None:
    """Truncated, mistyped, empty, and out-of-bounds ICOs fail closed."""
    icon = tmp_path / "invalid.ico"
    icon.write_bytes(payload)

    with pytest.raises(IconResourceError):
        parse_ico(icon)


@pytest.mark.skipif(sys.platform != "win32", reason="requires the Win32 resource API")
def test_real_pe_stamp_is_exact_and_precedes_checksum(tmp_path: Path) -> None:
    """A real PE keeps loading after stamping and its checksum binds icon bytes."""
    source = tmp_path / "source.exe"
    executable = tmp_path / "python.exe"
    shutil.copy2(sys.executable, source)

    checksum = publish_asset(source, executable, "x86_64-pc-windows-msvc")
    stamped = executable.read_bytes()

    verify_icon(executable, APPLICATION_ICON)
    assert stamped != source.read_bytes()
    assert (
        checksum.read_text(encoding="utf-8").split()[0]
        == hashlib.sha256(stamped).hexdigest()
    )
