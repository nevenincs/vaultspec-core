"""Trailing-whitespace autofix.

Strips trailing whitespace from every line. Idempotent. The
convention's row contract terminates the row sentence with a single
ASCII period; trailing spaces or tabs after the period are removed by
this autofix.
"""

from __future__ import annotations

__all__ = ["fix_trailing_whitespace"]


def fix_trailing_whitespace(source_text: str) -> str:
    """Strip trailing whitespace from every line in ``source_text``."""
    fixed_lines = [line.rstrip() for line in source_text.splitlines()]
    trailing = "\n" if source_text.endswith("\n") else ""
    return "\n".join(fixed_lines) + trailing
