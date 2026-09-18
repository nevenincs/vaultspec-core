"""Exact ICO parsing and Windows PE resource tests."""

from __future__ import annotations

import hashlib
import shutil
import struct
import sys
import time
from typing import TYPE_CHECKING

import pytest

from dev.binaries.build_pyapp import (
    APPLICATION_ICON,
    BINARIES,
    binary_version_info,
    publish_asset,
)
from dev.binaries.windows_icon import (
    RESOURCE_ATTEMPTS,
    TRANSIENT_WIN32_ERRORS,
    IconResourceError,
    Win32ResourceError,
    _retry_transient,
    parse_ico,
    verify_icon,
    verify_version_info,
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


def test_real_pe_stamp_is_exact_and_precedes_checksum(tmp_path: Path) -> None:
    """PE stamping works on Windows and rejects unavailable Win32 APIs elsewhere."""
    source = tmp_path / "source.exe"
    executable = tmp_path / "python.exe"
    shutil.copy2(sys.executable, source)

    if sys.platform != "win32":
        with pytest.raises(IconResourceError, match="Windows PE resources"):
            publish_asset(
                source,
                executable,
                "x86_64-pc-windows-msvc",
                BINARIES[0],
                "0.2.1",
            )
        return

    checksum = publish_asset(
        source,
        executable,
        "x86_64-pc-windows-msvc",
        BINARIES[0],
        "0.2.1",
    )
    stamped = executable.read_bytes()

    verify_icon(executable, APPLICATION_ICON)
    verify_version_info(
        executable,
        binary_version_info(BINARIES[0], "0.2.1", "x86_64-pc-windows-msvc"),
    )
    assert stamped != source.read_bytes()
    assert (
        checksum.read_text(encoding="utf-8").split()[0]
        == hashlib.sha256(stamped).hexdigest()
    )


def _no_wait(seconds: float) -> None:
    """Stand in for the backoff so the retry policy is tested, not the clock."""


@pytest.mark.parametrize("code", sorted(TRANSIENT_WIN32_ERRORS))
def test_a_held_executable_is_stamped_once_the_holder_lets_go(
    code: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scanner holding the image delays the commit, it does not fail it."""
    monkeypatch.setattr(time, "sleep", _no_wait)
    attempts = 0

    def commit() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < RESOURCE_ATTEMPTS:
            raise Win32ResourceError(f"committing resources failed: [{code}]", code)

    _retry_transient(commit)

    assert attempts == RESOURCE_ATTEMPTS


def test_a_holder_that_never_lets_go_fails_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrying is bounded: a permanent denial still stops the release."""
    monkeypatch.setattr(time, "sleep", _no_wait)
    attempts = 0

    def commit() -> None:
        nonlocal attempts
        attempts += 1
        raise Win32ResourceError("committing resources failed: [5]", 5)

    with pytest.raises(Win32ResourceError, match=r"\[5\]"):
        _retry_transient(commit)

    assert attempts == RESOURCE_ATTEMPTS


def test_a_permission_failure_is_not_retried() -> None:
    """Only the codes that mean "someone else has it" are worth waiting out."""
    attempts = 0

    def commit() -> None:
        nonlocal attempts
        attempts += 1
        raise Win32ResourceError("opening resources failed: [2]", 2)

    with pytest.raises(Win32ResourceError, match=r"\[2\]"):
        _retry_transient(commit)

    assert attempts == 1


def test_a_resource_mismatch_is_never_retried() -> None:
    """A wrong stamp is a defect in the payload, not a collision to wait out."""
    attempts = 0

    def commit() -> None:
        nonlocal attempts
        attempts += 1
        raise IconResourceError("primary icon group does not match")

    with pytest.raises(IconResourceError):
        _retry_transient(commit)

    assert attempts == 1
