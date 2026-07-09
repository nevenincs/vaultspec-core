"""Shared kebab-case feature/tag normalization for the CLI and MCP surfaces.

A vaultspec feature handle and every additional ``#tag`` is a kebab-case
token: lowercase letters, digits, and hyphens, opening on an alphanumeric.
That rule was written three times over - in ``vaultspec-core vault add``, in
the MCP ``create`` tool, and in the per-tag loop each shares - which is
exactly the divergence risk the ``mcp-tool-schema`` reconciliation removes.
This module is the one owner: :func:`normalize_feature_tag` strips a leading
``#``, lowercases and trims, rejects path-traversal, and validates the
canonical pattern, returning a typed :class:`NormalizeResult` instead of
printing or raising, so both a Typer verb and an MCP tool can render the
outcome in their own idiom.

The normalizer never fabricates a value it cannot validate: on any failure
it returns ``ok=False`` with a human-readable ``error`` and a ``None``
value, and the caller decides how to surface it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "KEBAB_CASE_PATTERN",
    "NormalizeResult",
    "normalize_feature_tag",
]

#: The canonical kebab-case token: opens on an alphanumeric, then any run of
#: lowercase letters, digits, and hyphens. Shared by the feature handle and
#: every additional ``#tag``.
KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: Path-traversal characters stripped/rejected before pattern validation, so
#: a normalized token can never escape a directory or inject a separator.
_TRAVERSAL_CHARS = re.compile(r"[/\\]")


@dataclass(frozen=True)
class NormalizeResult:
    """The typed outcome of normalizing one feature handle or tag token.

    Attributes:
        ok: ``True`` when *value* is a valid kebab-case token.
        value: The normalized token (no ``#`` prefix, lowercased) on
            success; ``None`` on failure.
        error: A human-readable failure summary on ``ok is False``; ``None``
            on success.
    """

    ok: bool
    value: str | None = None
    error: str | None = None


def normalize_feature_tag(raw: str, *, label: str = "feature tag") -> NormalizeResult:
    """Normalize and validate a kebab-case feature handle or ``#tag``.

    Strips a single leading ``#``, trims surrounding whitespace, lowercases,
    folds any path-separator into a hyphen and drops parent-directory
    tokens, then validates the canonical kebab-case pattern
    (:data:`KEBAB_CASE_PATTERN`). The returned :class:`NormalizeResult`
    carries the ``#``-free token on success (the caller re-applies ``#``
    where a stored tag needs it) and a rendered *label*-scoped message on
    failure.

    Args:
        raw: The user-supplied handle or tag (with or without a leading
            ``#``; case- and whitespace-insensitive).
        label: The noun used in the failure message (e.g. ``"feature tag"``
            or ``"tag"``), so a caller can scope the diagnostic to its
            surface.

    Returns:
        A :class:`NormalizeResult`: ``ok=True`` with the normalized value,
        or ``ok=False`` with an ``error`` and a ``None`` value.
    """
    cleaned = raw.lstrip("#").strip().lower()
    cleaned = _TRAVERSAL_CHARS.sub("-", cleaned).replace("..", "")

    if not cleaned:
        return NormalizeResult(
            ok=False,
            error=f"{label} is required (e.g. my-feature)",
        )

    if KEBAB_CASE_PATTERN.match(cleaned) is None:
        return NormalizeResult(
            ok=False,
            error=(
                f"Invalid {label} '{raw}'. "
                "Must be kebab-case (lowercase, digits, hyphens)."
            ),
        )

    return NormalizeResult(ok=True, value=cleaned)
