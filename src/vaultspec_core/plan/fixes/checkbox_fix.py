"""Checkbox-spacing autofix.

Normalises non-canonical checkbox glyphs to the convention's two-state
form: ``- [ ]`` open, ``- [x]`` closed. Any other state (``[]``,
``[X]``, etc.) is replaced with the closest canonical equivalent.
Idempotent: a second run on already-canonical text is a no-op.
"""

from __future__ import annotations

import re

__all__ = ["fix_checkbox_spacing"]


_RE_NO_SPACE = re.compile(r"^- \[\]")
_RE_UPPER_X = re.compile(r"^- \[X\]")


def fix_checkbox_spacing(source_text: str) -> str:
    """Normalise checkbox glyphs on every list-row line.

    - ``- []``     -> ``- [ ]``
    - ``- [X]``    -> ``- [x]``

    Any other variant (``[~]``, ``[/]``, etc.) is left in place; the
    convention defines those as out-of-contract states and the writer
    must resolve them manually.
    """
    fixed_lines: list[str] = []
    for line in source_text.splitlines():
        rewritten = _RE_NO_SPACE.sub("- [ ]", line)
        rewritten = _RE_UPPER_X.sub("- [x]", rewritten)
        fixed_lines.append(rewritten)
    trailing = "\n" if source_text.endswith("\n") else ""
    return "\n".join(fixed_lines) + trailing
