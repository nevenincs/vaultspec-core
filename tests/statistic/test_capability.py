"""Tests for the declared-capability denominator parser.

These assert the exact verb-path and flag denominator the parser yields from a
committed, redacted CLI-reference fixture, and that the advisory membership
queries behave correctly for declared versus undeclared verbs and known versus
unknown flags. The fixture is synthetic: no personal data, usernames, or
absolute paths appear, and the parser is always pointed at it by an explicit
path parameter so no operator machine state is touched.
"""

from __future__ import annotations

from pathlib import Path

from statistic.metrics.capability import (
    CapabilityInventory,
    parse_capability_inventory,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "cli_reference.md"


def _inventory() -> CapabilityInventory:
    """Parse the committed fixture into an inventory."""
    return parse_capability_inventory(_FIXTURE)


def test_verb_paths_match_the_fixture_denominator() -> None:
    """The parser yields exactly the in-marker verb paths, and no more."""
    inventory = _inventory()
    assert inventory.verb_paths == frozenset(
        {
            ("status",),
            ("sync",),
            ("vault", "list"),
            ("vault", "add"),
            ("vault", "check", "all"),
            ("vault", "check", "references"),
            ("vault", "plan", "step", "check"),
            ("vault", "plan", "tier", "demote"),
        }
    )


def test_bullets_outside_the_markers_are_excluded() -> None:
    """A bullet outside the generated markers never enters the denominator."""
    inventory = _inventory()
    assert not inventory.declares_verb_path(("should-not-appear",))


def test_declared_verb_membership() -> None:
    """A declared verb path is declared; an undeclared one is not."""
    inventory = _inventory()
    assert inventory.declares_verb_path(("vault", "check", "all"))
    assert not inventory.declares_verb_path(("vault", "check", "nonexistent"))


def test_declared_flags_from_inline_backticks() -> None:
    """Inline backtick flags are collected per verb path, including wraps."""
    inventory = _inventory()
    assert inventory.declared_flags(("vault", "list")) == frozenset({"--feature", "-f"})
    assert inventory.declared_flags(("vault", "check", "all")) == frozenset({"--fix"})
    assert inventory.declared_flags(("vault", "check", "references")) == frozenset(
        {"--strict"}
    )


def test_flag_membership_is_advisory() -> None:
    """A declared flag is declared; an unknown one is a candidate miss."""
    inventory = _inventory()
    assert inventory.declares_flag(("vault", "list"), "--feature")
    assert inventory.declares_flag(("vault", "list"), "-f")
    assert not inventory.declares_flag(("vault", "list"), "--nonexistent")


def test_verb_without_declared_flags_maps_to_empty_set() -> None:
    """A verb path with no inline flags declares an empty flag set."""
    inventory = _inventory()
    assert inventory.declared_flags(("status",)) == frozenset()
    assert not inventory.declares_flag(("status",), "--anything")


def test_undeclared_verb_flag_query_is_false() -> None:
    """A flag query against an undeclared verb path is False, not an error."""
    inventory = _inventory()
    assert not inventory.declares_flag(("no", "such", "verb"), "--fix")
    assert inventory.declared_flags(("no", "such", "verb")) == frozenset()
