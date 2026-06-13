"""Commit-linkage trailer vocabulary: parse, format, and validate.

This module owns the vaultspec commit-linkage trailer convention in one place,
mirroring how :mod:`vaultspec_core.plan.display_path` and
:mod:`vaultspec_core.plan.identifiers` own their formats. The trailer is opt-in
enrichment for tooling that correlates git commits to vault records: a commit
may declare its vaultspec association explicitly through a git trailer so a
downstream consumer resolves that correlation deterministically instead of
heuristically (path overlap, time windows, same-day co-activity).

Two trailer keys are defined:

- ``Vaultspec-Step`` carries a Step display path (``S06``, ``P02.S06``,
  ``W01.P02.S06``) or the phase-only form (``P02``, ``W01.P02``), matching what
  :mod:`vaultspec_core.plan.display_path` produces at every tier.
- ``Vaultspec-Feature`` carries a feature tag in kebab-case, with an optional
  leading ``#`` (the frontmatter-stored form).

The convention is advisory and never load-bearing (see the commit-linkage ADR
``2026-06-13-commit-linkage-adr``): absence or malformation of a trailer must
never block a commit or fail a core command. Everything here is a pure, offline
string operation over the trailer values; no git history is read to validate a
single message. The CLI verb that wraps :func:`validate_message` always exits
zero so it is safe to install as an advisory ``commit-msg`` hook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "FEATURE_TRAILER_KEY",
    "STEP_TRAILER_KEY",
    "Trailer",
    "TrailerProblem",
    "format_feature_trailer",
    "format_step_trailer",
    "parse_message",
    "validate_message",
    "validate_value",
]

#: Trailer key carrying a Step (or Phase) display path.
STEP_TRAILER_KEY = "Vaultspec-Step"

#: Trailer key carrying a feature tag.
FEATURE_TRAILER_KEY = "Vaultspec-Feature"

# A full Step display path: optional Wave and Phase ancestors, then the Step.
# Mirrors the tier-dependent forms display_path.py emits (S06 / P02.S06 /
# W01.P02.S06). Step ids never carry an alpha suffix; Phase/Wave ids may.
_STEP_VALUE = re.compile(r"^(?:W\d{2,}\.)?(?:P\d{2,}[a-z]?\.)?S\d{2,}$")

# The phase-only form, so a commit that spans a whole Phase can still link.
_PHASE_VALUE = re.compile(r"^(?:W\d{2,}\.)?P\d{2,}[a-z]?$")

# A feature tag in kebab-case, with the leading '#' optional (the stored
# frontmatter form carries the '#').
_FEATURE_VALUE = re.compile(r"^#?[a-z0-9][a-z0-9-]*$")

# A git-trailer line: ``Token: value`` where the token is a hyphen-joined word.
# Matched case-insensitively on the key; the value is stripped of surrounding
# whitespace. This is deliberately permissive about which token it matches so
# the caller can pick out only the vaultspec keys.
_TRAILER_LINE = re.compile(
    r"^(?P<key>[A-Za-z][A-Za-z0-9-]*):[ \t]*(?P<value>.*?)[ \t]*$"
)

# The vaultspec trailer keys, lower-cased for case-insensitive matching.
_KNOWN_KEYS: dict[str, str] = {
    STEP_TRAILER_KEY.lower(): STEP_TRAILER_KEY,
    FEATURE_TRAILER_KEY.lower(): FEATURE_TRAILER_KEY,
}


@dataclass(frozen=True)
class Trailer:
    """One vaultspec trailer found in a commit message.

    Attributes:
        key: The canonical trailer key (:data:`STEP_TRAILER_KEY` or
            :data:`FEATURE_TRAILER_KEY`), normalised regardless of the
            case the author typed.
        value: The trailer value with surrounding whitespace stripped.
        line_number: 1-based line where the trailer was found in the message.
    """

    key: str
    value: str
    line_number: int


@dataclass(frozen=True)
class TrailerProblem:
    """A malformed vaultspec trailer reported by :func:`validate_message`.

    Attributes:
        key: The canonical trailer key whose value failed validation.
        value: The offending value as it appeared in the message.
        line_number: 1-based line where the trailer was found.
        reason: A human-readable description of why the value is invalid.
    """

    key: str
    value: str
    line_number: int
    reason: str


def parse_message(message: str) -> list[Trailer]:
    """Return every vaultspec trailer found in a commit *message*.

    Scans the message line by line for ``Vaultspec-Step:`` and
    ``Vaultspec-Feature:`` lines (key matched case-insensitively) and returns
    them in document order. Non-vaultspec trailer lines are ignored. This is a
    pure string scan: it does not require the trailers to live in the message's
    trailing block, so a malformed message still yields whatever vaultspec
    trailers it contains for validation.

    Args:
        message: The full commit-message text.

    Returns:
        The vaultspec trailers found, in the order they appear.
    """
    trailers: list[Trailer] = []
    for index, line in enumerate(message.splitlines(), start=1):
        match = _TRAILER_LINE.match(line)
        if match is None:
            continue
        canonical = _KNOWN_KEYS.get(str(match.group("key")).lower())
        if canonical is None:
            continue
        trailers.append(
            Trailer(
                key=canonical,
                value=str(match.group("value")),
                line_number=index,
            )
        )
    return trailers


def validate_value(key: str, value: str) -> str | None:
    """Validate a single trailer *value* for *key*.

    Args:
        key: A canonical trailer key (:data:`STEP_TRAILER_KEY` or
            :data:`FEATURE_TRAILER_KEY`).
        value: The candidate value.

    Returns:
        ``None`` when the value is well-formed for the key, otherwise a
        human-readable reason describing the expected shape. An unknown key
        also returns a reason rather than raising.
    """
    if key == STEP_TRAILER_KEY:
        if _STEP_VALUE.match(value) or _PHASE_VALUE.match(value):
            return None
        return (
            "expected a Step or Phase display path "
            "(e.g. S06, P02.S06, W01.P02.S06, or P02)"
        )
    if key == FEATURE_TRAILER_KEY:
        if _FEATURE_VALUE.match(value):
            return None
        return (
            "expected a kebab-case feature tag (e.g. auth-refactor or #auth-refactor)"
        )
    return f"unknown vaultspec trailer key {key!r}"


def validate_message(message: str) -> list[TrailerProblem]:
    """Return the malformed vaultspec trailers in a commit *message*.

    A clean message, or a message carrying no vaultspec trailer at all, yields
    an empty list. Each vaultspec trailer whose value fails
    :func:`validate_value` is reported as one :class:`TrailerProblem`. This
    function never raises and never inspects anything beyond the message text,
    so its caller can safely report problems and exit zero (the
    enrichment-not-prerequisite constraint).

    Args:
        message: The full commit-message text.

    Returns:
        One :class:`TrailerProblem` per malformed trailer, in document order.
    """
    problems: list[TrailerProblem] = []
    for trailer in parse_message(message):
        reason = validate_value(trailer.key, trailer.value)
        if reason is not None:
            problems.append(
                TrailerProblem(
                    key=trailer.key,
                    value=trailer.value,
                    line_number=trailer.line_number,
                    reason=reason,
                )
            )
    return problems


def format_step_trailer(display_path: str) -> str:
    """Return a well-formed ``Vaultspec-Step`` trailer line for *display_path*.

    Args:
        display_path: A Step display path (``S06``, ``P02.S06``,
            ``W01.P02.S06``) or the phase-only form (``P02``, ``W01.P02``).

    Returns:
        The trailer line ``Vaultspec-Step: <display_path>`` (no trailing
        newline).

    Raises:
        ValueError: When *display_path* is not a valid Step or Phase display
            path. Emission only ever produces well-formed trailers.
    """
    reason = validate_value(STEP_TRAILER_KEY, display_path)
    if reason is not None:
        raise ValueError(f"invalid {STEP_TRAILER_KEY} value {display_path!r}: {reason}")
    return f"{STEP_TRAILER_KEY}: {display_path}"


def format_feature_trailer(feature: str) -> str:
    """Return a well-formed ``Vaultspec-Feature`` trailer line for *feature*.

    The value is emitted as a bare kebab-case tag: a single leading ``#`` is
    stripped so the trailer carries the same token the feature is known by
    elsewhere, without the frontmatter-only ``#`` prefix.

    Args:
        feature: A feature tag in kebab-case, with or without a leading ``#``.

    Returns:
        The trailer line ``Vaultspec-Feature: <tag>`` (no trailing newline).

    Raises:
        ValueError: When *feature* is not a valid kebab-case feature tag.
    """
    reason = validate_value(FEATURE_TRAILER_KEY, feature)
    if reason is not None:
        raise ValueError(f"invalid {FEATURE_TRAILER_KEY} value {feature!r}: {reason}")
    return f"{FEATURE_TRAILER_KEY}: {feature.lstrip('#')}"
