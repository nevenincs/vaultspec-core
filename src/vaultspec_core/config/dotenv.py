"""Read one named variable from a dotenv file, and nothing else from it.

Core configuration comes from the process environment, and core loads no
``.env`` at runtime. The one exception is a credential that a workspace may
keep in its own ``.env`` when it runs core as a project dependency. That file
is repository content, so this reader is deliberately not a loader:

- It returns the value of the single variable a caller names. Nothing else in
  the file is read into the process, so a cloned repository's ``.env`` cannot
  reach any other setting.
- It supports the common shapes only: blank lines, ``#`` comment lines, an
  optional ``export`` prefix, an unquoted value with an optional trailing
  ``# comment``, and a value wrapped in single or double quotes. There is no
  interpolation, no escape processing and no multi-line value; a value that
  opens a quote and never closes it on its own line is treated as absent
  rather than guessed at.
- When a name is assigned more than once, the last assignment wins, as it does
  when a shell sources the file.
- It never logs. The values it exists to read are credentials.

A missing, unreadable or undecodable file, an absent name and a blank value
all read as ``None``: for a caller choosing between sources, each means the
same thing - this source supplies nothing.
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
