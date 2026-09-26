"""Literal dotenv readers; neither evaluates shell code nor interpolates variables.

The legacy credential reader selects one named value and treats blanks as absent.
Explicit imports use strict assignment parsing, preserve blanks, and round-trip
quoted single-line values. No reader modifies the process environment.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["read_dotenv_value"]

#: ``NAME=value`` with an optional ``export`` prefix and optional spaces
#: around the name and the ``=``.
_ASSIGNMENT: Final = re.compile(
    r"^(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$"
)

#: A trailing comment on an unquoted value: a ``#`` preceded by whitespace.
_TRAILING_COMMENT: Final = re.compile(r"\s+#.*$")


def _unquote(raw: str) -> str | None:
    """Return the value an assignment's right-hand side denotes.

    Args:
        raw: The text after ``=``, with surrounding whitespace removed.

    Returns:
        The value between matching quotes, the unquoted value without its
        trailing comment, or ``None`` when a quote is opened and not closed.
    """
    if raw[:1] in ("'", '"'):
        closing = raw.find(raw[0], 1)
        if closing == -1:
            return None
        return raw[1:closing]
    return _TRAILING_COMMENT.sub("", raw)


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse a bounded import without interpolation, retaining explicit blanks.

    Double quotes support escaped backslashes and quotes. Other backslashes
    stay literal (including Windows paths). Errors never repeat input text.
    """
    values: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        if match is None:
            raise ValueError(f"Invalid environment assignment at line {number}")
        raw = match.group("value").strip()
        value = _parse_import_value(raw)
        if value is None:
            raise ValueError(f"Invalid environment value at line {number}")
        values[match.group("name")] = value
    return values


def _parse_import_value(raw: str) -> str | None:
    if raw[:1] not in ("'", '"'):
        return _TRAILING_COMMENT.sub("", raw).rstrip()
    quote = raw[0]
    value: list[str] = []
    index = 1
    while index < len(raw):
        char = raw[index]
        if char == quote:
            tail = raw[index + 1 :].strip()
            return "".join(value) if not tail or tail.startswith("#") else None
        if (
            quote == '"'
            and char == "\\"
            and index + 1 < len(raw)
            and raw[index + 1] in ('"', "\\")
        ):
            index += 1
            char = raw[index]
        value.append(char)
        index += 1
    return None


def format_dotenv(values: dict[str, str]) -> str:
    """Encode single-line settings using literal, round-trippable quoting."""
    lines = []
    for name, value in sorted(values.items()):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{name}="{escaped}"\n')
    return "".join(lines)


def read_dotenv_value(path: Path, name: str) -> str | None:
    """Read the value of *name* from the dotenv file at *path*.

    Args:
        path: The dotenv file to read.
        name: The variable whose value to return.

    Returns:
        The value as written, without surrounding quotes, or ``None`` when the
        file is missing or unreadable, *name* is not assigned, or its value is
        blank or malformed.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None

    value: str | None = None
    for line in text.splitlines():
        match = _ASSIGNMENT.match(line.strip())
        if match is None or match.group("name") != name:
            continue
        value = _unquote(match.group("value").strip())
    if value is None or not value.strip():
        return None
    return value
