"""Tests for the shared kebab-case feature/tag normalizer.

These assert the pure-function contract of
:func:`~vaultspec_core.vaultcore.normalize.normalize_feature_tag`: it strips a
leading ``#``, lowercases, trims, folds path separators, and validates the
canonical kebab-case pattern - returning a typed result rather than raising.
The regression guarded here is the silent ``..`` deletion (``a..b`` -> ``ab``)
that could mask a typo into a valid-but-different token; the fix rejects any
residual ``.`` instead. No mocks, stubs, or skips: the function is pure.
"""

from __future__ import annotations

import pytest

from vaultspec_core.vaultcore.normalize import normalize_feature_tag

pytestmark = [pytest.mark.unit]


def test_plain_kebab_token_normalizes() -> None:
    """A clean kebab-case handle passes through unchanged and #-free."""
    result = normalize_feature_tag("my-feature")
    assert result.ok is True
    assert result.value == "my-feature"
    assert result.error is None


def test_leading_hash_and_case_are_folded() -> None:
    """A leading ``#`` and upper case are normalized away."""
    result = normalize_feature_tag("#My-Feature")
    assert result.ok is True
    assert result.value == "my-feature"


def test_surrounding_whitespace_and_case_are_folded() -> None:
    """Surrounding whitespace is trimmed and the token is lowercased."""
    result = normalize_feature_tag("  My-Feature  ")
    assert result.ok is True
    assert result.value == "my-feature"


def test_empty_after_stripping_is_rejected() -> None:
    """A bare ``#`` (empty after stripping) fails with a required-field error."""
    result = normalize_feature_tag("#")
    assert result.ok is False
    assert result.value is None
    assert "required" in (result.error or "")


def test_double_dot_is_rejected_not_silently_repaired() -> None:
    """``a..b`` is rejected outright rather than collapsed into ``ab``.

    Deleting the ``..`` would turn a typo into a valid-but-different token; the
    canonical pattern forbids ``.`` so the residual dot fails validation and no
    value is fabricated.
    """
    result = normalize_feature_tag("a..b")
    assert result.ok is False
    assert result.value is None
    assert result.error is not None


def test_single_dot_is_rejected() -> None:
    """A single embedded ``.`` (``a.b``) also fails the kebab pattern."""
    result = normalize_feature_tag("a.b")
    assert result.ok is False
    assert result.value is None


def test_traversal_sequence_is_rejected() -> None:
    """A ``../x`` traversal attempt still fails after separator folding.

    The path separator folds to a hyphen (``..-x``), which opens on ``.`` and
    carries a dot, so the kebab pattern rejects it - the token can never escape
    a directory.
    """
    for raw in ("../x", "..\\x", "a/../b"):
        result = normalize_feature_tag(raw)
        assert result.ok is False, raw
        assert result.value is None, raw


def test_label_scopes_the_failure_message() -> None:
    """The *label* argument scopes the rendered diagnostic to the surface."""
    result = normalize_feature_tag("Bad Tag", label="tag")
    assert result.ok is False
    assert "tag" in (result.error or "")
