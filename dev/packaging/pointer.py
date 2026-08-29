"""Refuse a channel manifest that would move a release pointer backward.

A committed Scoop manifest or Homebrew formula is a POINTER: it names one
version and pins its digests, and a user's package manager acts on whatever
is committed right now. Overwriting it with an older release therefore does
not merely churn a file - it un-publishes the current version for everyone
who installs next.

The release job runs after a long build matrix, so a stale re-run of an older
tag can reach this point long after a newer tag has already landed. That is
the case this guard exists for.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

#: ``version "0.1.60"`` as a Homebrew formula writes it.
_FORMULA_VERSION = re.compile(r'^\s*version\s+"(?P<version>[^"]+)"', re.MULTILINE)


class PointerError(RuntimeError):
    """The requested bump would regress a published release pointer."""


def _version_key(version: str) -> tuple[int, ...]:
    """Return a comparable key for a dotted release version.

    Only the numeric prefix is compared. Pre-release suffixes are deliberately
    not ordered here: this guard answers "is this strictly older?", and a
    version it cannot order is one it must not block on.
    """
    parts: list[int] = []
    for chunk in version.split("."):
        digits = re.match(r"\d+", chunk)
        if digits is None:
            break
        parts.append(int(digits.group()))
    return tuple(parts)


def existing_scoop_version(path: Path) -> str | None:
    """Return the version a committed Scoop manifest points at, if any."""
    if not path.is_file():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    version = manifest.get("version")
    return str(version) if version else None


def existing_homebrew_version(path: Path) -> str | None:
    """Return the version a committed Homebrew formula points at, if any."""
    if not path.is_file():
        return None
    match = _FORMULA_VERSION.search(path.read_text(encoding="utf-8"))
    return match["version"] if match else None


def check_forward(current: str | None, incoming: str) -> None:
    """Raise :class:`PointerError` when ``incoming`` is older than ``current``.

    An absent, unparseable, or equal pointer is allowed through: the first
    publishes a channel that had none, and re-publishing the same version is
    how a partially failed release converges.
    """
    if current is None or current == incoming:
        return
    current_key, incoming_key = _version_key(current), _version_key(incoming)
    if not current_key or not incoming_key:
        return
    if incoming_key < current_key:
        raise PointerError(
            f"channel is at {current}; refusing to move the pointer backward "
            f"to {incoming}",
        )
