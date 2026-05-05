"""Canonical-identifier extraction, next-available counters, and validation.

The convention ADR mandates that ``S##``/``P##``/``W##`` are flat,
per-document, append-only, and immutable. New identifiers are always
next-available; deleted identifiers leave gaps that are never reused.
This module computes those values from a parsed :class:`Plan` and
surfaces violations (duplicates, padding drift) as typed errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "DuplicateIdentifierError",
    "IdentifierInventory",
    "PaddingViolation",
    "extract_inventory",
    "next_available_phase",
    "next_available_step",
    "next_available_wave",
    "validate_identifiers",
]


_CONTAINER_PATTERN = re.compile(r"^([SPW])(\d{2,})$")


class DuplicateIdentifierError(ValueError):
    """Raised when the same canonical identifier appears on multiple rows."""


@dataclass
class PaddingViolation:
    """One identifier whose width violates the two-digit-minimum rule.

    Attributes:
        kind: ``S``, ``P``, or ``W``.
        value: The identifier as it appears in the document.
        line_number: 1-based source line where the violation was observed.
    """

    kind: str
    value: str
    line_number: int


@dataclass
class IdentifierInventory:
    """Collected canonical identifiers from a parsed plan.

    Attributes:
        steps: Step canonical ids in document order.
        phases: Phase canonical ids in document order.
        waves: Wave canonical ids in document order.
        padding_violations: Identifiers whose width is below two digits or
            otherwise non-conforming.
    """

    steps: list[str]
    phases: list[str]
    waves: list[str]
    padding_violations: list[PaddingViolation]


def extract_inventory(plan: Plan) -> IdentifierInventory:
    """Return every canonical identifier observed in ``plan``.

    Args:
        plan: A parsed :class:`Plan` model.

    Returns:
        :class:`IdentifierInventory` populated with the document's
        identifiers in document order.
    """
    steps = [step.canonical_id for step in plan.steps]
    phases = [phase.canonical_id for phase in plan.phases]
    waves = [wave.canonical_id for wave in plan.waves]
    violations = _collect_padding_violations(plan)
    return IdentifierInventory(
        steps=steps,
        phases=phases,
        waves=waves,
        padding_violations=violations,
    )


def validate_identifiers(plan: Plan) -> None:
    """Verify the plan's canonical identifiers are unique within their kind.

    The convention prohibits re-use of retired identifiers, so any
    duplicate within a single document is a contract violation. Padding
    violations are reported via :class:`PaddingViolation` rather than
    raised; the caller decides whether to fail or warn.

    Args:
        plan: Parsed :class:`Plan` model.

    Raises:
        DuplicateIdentifierError: When the same canonical identifier
            appears more than once for the same container kind.
    """
    inventory = extract_inventory(plan)
    _raise_on_duplicate(inventory.steps, kind="Step")
    _raise_on_duplicate(inventory.phases, kind="Phase")
    _raise_on_duplicate(inventory.waves, kind="Wave")


def next_available_step(plan: Plan) -> str:
    """Return the next-available ``S##`` identifier for the plan.

    The next-available value is one greater than the maximum of the
    live and retired Step numbers, ensuring append-only allocation.
    Gaps left by retirement are preserved (never reused).

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        Zero-padded canonical identifier (``S01``, ``S02``, ...,
        ``S117``). The width is at least two digits and widens as the
        counter grows.
    """
    return _next_available_id(
        existing=[s.canonical_id for s in plan.steps],
        retired=plan.retired_step_ids,
        prefix="S",
    )


def next_available_phase(plan: Plan) -> str:
    """Return the next-available ``P##`` identifier for the plan.

    Skips both live and retired Phase numbers so removed identifiers
    are never reissued.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        Zero-padded canonical Phase identifier.
    """
    return _next_available_id(
        existing=[p.canonical_id for p in plan.phases],
        retired=plan.retired_phase_ids,
        prefix="P",
    )


def next_available_wave(plan: Plan) -> str:
    """Return the next-available ``W##`` identifier for the plan.

    Skips both live and retired Wave numbers.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        Zero-padded canonical Wave identifier.
    """
    return _next_available_id(
        existing=[w.canonical_id for w in plan.waves],
        retired=plan.retired_wave_ids,
        prefix="W",
    )


def _next_available_id(
    *,
    existing: list[str],
    retired: set[str],
    prefix: str,
) -> str:
    """Compute the next-available identifier for the given container kind.

    The minimum padding is two digits per the convention; the field
    widens automatically once the counter exceeds 99. Both live and
    retired identifiers contribute to the maximum so gaps left by
    retirement are never reused.
    """
    numbers = [_extract_number(identifier) for identifier in existing]
    numbers.extend(_extract_number(identifier) for identifier in retired)
    next_number = (max(numbers) + 1) if numbers else 1
    width = max(2, len(str(next_number)))
    return f"{prefix}{next_number:0{width}d}"


def _extract_number(identifier: str) -> int:
    """Extract the numeric tail from an identifier; raises on malformed input."""
    match = _CONTAINER_PATTERN.match(identifier)
    if match is None:
        msg = f"Identifier {identifier!r} does not match the canonical S/P/W##... shape"
        raise ValueError(msg)
    return int(match.group(2))


def _raise_on_duplicate(identifiers: list[str], *, kind: str) -> None:
    """Raise :class:`DuplicateIdentifierError` when ``identifiers`` has duplicates."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for identifier in identifiers:
        if identifier in seen:
            duplicates.append(identifier)
        else:
            seen.add(identifier)
    if duplicates:
        msg = (
            f"{kind} canonical identifier(s) appear multiple times: "
            f"{sorted(set(duplicates))}"
        )
        raise DuplicateIdentifierError(msg)


def _collect_padding_violations(plan: Plan) -> list[PaddingViolation]:
    """Return identifiers whose width is below the two-digit minimum.

    The parser regex enforces the minimum on Step rows it accepts, but
    legacy plans or hand-edits can produce a Phase / Wave heading with
    a single-digit identifier. Surface those for the caller's
    reporting layer.
    """
    violations: list[PaddingViolation] = []
    for step in plan.steps:
        if _violates_padding(step.canonical_id):
            violations.append(
                PaddingViolation(
                    kind="S",
                    value=step.canonical_id,
                    line_number=step.line_number,
                ),
            )
    for phase in plan.phases:
        if _violates_padding(phase.canonical_id):
            violations.append(
                PaddingViolation(
                    kind="P",
                    value=phase.canonical_id,
                    line_number=phase.line_number,
                ),
            )
    for wave in plan.waves:
        if _violates_padding(wave.canonical_id):
            violations.append(
                PaddingViolation(
                    kind="W",
                    value=wave.canonical_id,
                    line_number=wave.line_number,
                ),
            )
    return violations


def _violates_padding(identifier: str) -> bool:
    """Return ``True`` when ``identifier`` violates the minimum-padding rule."""
    match = _CONTAINER_PATTERN.match(identifier)
    if match is None:
        return True
    return len(match.group(2)) < 2
