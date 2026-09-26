"""The one vocabulary every vaultspec package reads environment values with.

One boolean table, one blank rule and one rejection message, so the same text
in the same variable means the same thing in every package and every process
kind. A package that spawns workers re-imports this chain in each worker, so
this module imports nothing beyond the standard library and nothing from
:mod:`vaultspec_core` itself: it must stay cheap enough to import per worker.

The rules it fixes:

- **Booleans.** ``1``, ``true``, ``yes`` and ``on`` against ``0``, ``false``,
  ``no`` and ``off``, stripped and case-folded.
- **Blank.** A blank value is unset for every product-owned variable, and
  falls through to the next source rather than reading as off.
- **Invalid.** An unrecognised value is refused, naming the variable, the
  value and the shape expected. A secret's value is withheld from that
  message: a rejected credential is still a credential.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "BOOL_SHAPE",
    "FALSE_TOKENS",
    "TRUE_TOKENS",
    "is_blank",
    "parse_bool",
    "rejection",
]

#: Words that mean on, stripped and case-folded.
TRUE_TOKENS: Final = frozenset({"1", "true", "yes", "on"})

#: Words that mean off, stripped and case-folded. Blank is not among them:
#: a blank value is unset, not off.
FALSE_TOKENS: Final = frozenset({"0", "false", "no", "off"})

#: What a rejection message names as the accepted shape of a boolean.
BOOL_SHAPE: Final = "one of " + ", ".join(sorted(TRUE_TOKENS | FALSE_TOKENS))

#: What a message shows in place of a secret's value.
_REDACTED: Final = "<redacted>"


def is_blank(raw: str | None) -> bool:
    """Return whether *raw* supplies nothing.

    Args:
        raw: A value as read from an environment or a file, or ``None`` when
            the source did not set it at all.

    Returns:
        ``True`` when the value is unset or whitespace only.
    """
    return raw is None or not raw.strip()


def parse_bool(raw: str) -> bool | None:
    """Return the boolean *raw* denotes, or ``None`` when it denotes none.

    Args:
        raw: A value as read from an environment or a file. Surrounding
            whitespace and letter case are not significant.

    Returns:
        ``True`` or ``False`` for a recognised word; ``None`` for anything
        else, blank included, which the caller resolves as unset or refuses.
    """
    token = raw.strip().casefold()
    if token in TRUE_TOKENS:
        return True
    if token in FALSE_TOKENS:
        return False
    return None


def rejection(
    where: str,
    shape: str,
    value: object,
    *,
    secret: bool = False,
) -> ValueError:
    """Build the one message an unusable value is refused with.

    Args:
        where: What carried the value, as an operator would name it - an
            environment variable name, typically.
        shape: What would have been accepted, for example :data:`BOOL_SHAPE`.
        value: The value that was refused.
        secret: If ``True``, *value* is a credential and is withheld from the
            message; the caller still learns which name was unusable.

    Returns:
        The error to raise, or to wrap in a package's own error type.
    """
    shown = _REDACTED if secret else repr(value)
    return ValueError(f"{where} must be {shape}, got {shown}")
