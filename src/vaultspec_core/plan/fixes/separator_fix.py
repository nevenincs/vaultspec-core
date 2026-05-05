"""Separator-normalisation autofix.

Replaces every em-dash (U+2014) and en-dash (U+2013) with the
canonical ASCII spaced hyphen ``" - "``. The replacement collapses
adjacent whitespace so the output always has exactly one space on
each side of the hyphen. Idempotent.
"""

from __future__ import annotations

import re

__all__ = ["fix_separator"]


# Unicode-name escapes keep this source from itself tripping the
# RUF001 / RUF003 ambiguous-character lints.
_EM_DASH = "\N{EM DASH}"
_EN_DASH = "\N{EN DASH}"

_RE_EM_OR_EN = re.compile(rf"\s*[{_EM_DASH}{_EN_DASH}]\s*")


def fix_separator(source_text: str) -> str:
    """Replace forbidden dashes with ``' - '`` (ASCII spaced hyphen)."""
    return _RE_EM_OR_EN.sub(" - ", source_text)
