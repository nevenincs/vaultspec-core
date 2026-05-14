"""Identifier-hygiene detection rule (``PLAN020``-``PLAN022``).

Validates canonical identifiers against the convention ADR's
*Identifiers and addressing* section:

- ``PLAN020 padding-violation`` (error): an identifier's numeric tail
  is shorter than the two-digit minimum.
- ``PLAN021 duplicate-identifier`` (error): the same canonical
  identifier appears on multiple rows or container headings.
- ``PLAN022 non-monotonic-id`` (warning): canonical identifiers are
  not strictly monotonically increasing in document order. This is
  not a hard violation (the writer may have inserted a Step between
  existing rows on purpose, leaving a higher canonical id earlier in
  the document) but the warning surfaces for review.
- ``PLAN023 alpha-suffix-id`` (warning): a Wave or Phase identifier
  uses an alpha suffix. Lowercase suffixes are supported for stable
  insertion; uppercase suffixes should be canonicalised to lowercase.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vaultspec_core.plan.checks._base import Finding, Severity
from vaultspec_core.plan.identifiers import extract_inventory

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["check_identifiers"]


_RE_UNDERPADDED_HEADING_ID = re.compile(
    r"^(?P<lead>#{2,3} +(?:Wave|Phase) +)`(?P<token>[WP]\d[A-Za-z]?)`",
)
_RE_ALPHA_SUFFIX_CONTAINER_ID = re.compile(r"(?P<token>[WP]\d{2,}[A-Za-z])")
_RE_ALPHA_SUFFIX_STEP_ID = re.compile(r"`(?P<token>S\d{2,}[A-Za-z])`")


def check_identifiers(plan: Plan, source_text: str = "") -> list[Finding]:
    """Detect padding violations, duplicates, and non-monotonic ids.

    Args:
        plan: Parsed :class:`Plan`. The model's container lists drive
            the duplicate / non-monotonic checks.
        source_text: Raw markdown body. Required for the parallel
            heading scan that catches single-digit Wave / Phase
            identifiers. The strict parser regex requires a two-digit
            minimum and would otherwise drop these headings silently,
            denying the model the line numbers needed to fire
            ``PLAN020`` for them.
    """
    inventory = extract_inventory(plan)
    findings: list[Finding] = []

    for violation in inventory.padding_violations:
        findings.append(
            Finding(
                code="PLAN020",
                severity=Severity.ERROR,
                message=(
                    f"{violation.kind}-identifier '{violation.value}' "
                    "violates the two-digit minimum padding rule."
                ),
                line_number=violation.line_number,
                fix_hint=(
                    "Pad the numeric tail to at least two digits; the "
                    "convention forbids retroactively re-padding existing "
                    "identifiers, so this typically requires removing the "
                    "violating row and re-creating it via "
                    "'vaultspec-core vault plan step add'."
                ),
                autofixable=False,
            ),
        )

    findings.extend(
        _detect_duplicates(inventory.steps, kind="Step", line_lookup=plan.steps),
    )
    findings.extend(
        _detect_duplicates(inventory.phases, kind="Phase", line_lookup=plan.phases),
    )
    findings.extend(
        _detect_duplicates(inventory.waves, kind="Wave", line_lookup=plan.waves),
    )

    findings.extend(_detect_non_monotonic(inventory.steps, kind="Step"))
    findings.extend(_detect_underpadded_headings(source_text))
    findings.extend(_detect_alpha_suffixes(source_text))
    findings.extend(_detect_step_alpha_suffixes(source_text))
    findings.extend(_detect_underpadded_retired_ids(plan))

    return findings


def _detect_underpadded_retired_ids(plan: Plan) -> list[Finding]:
    """Yield PLAN020 findings for retirement-ledger tokens below two digits.

    The ledger captures retired canonical ids via the lenient ``[SPW]\\d+``
    pattern so a sub-canonical width survives parsing rather than being
    silently dropped. Surface every such token as an ``ERROR`` so the
    writer can either widen the live id (which is forbidden retroactively
    and therefore implies removing the row) or correct the ledger.
    """
    findings: list[Finding] = []
    retired_by_kind = (
        ("Wave", plan.retired_wave_ids),
        ("Phase", plan.retired_phase_ids),
        ("Step", plan.retired_step_ids),
    )
    for kind, retired in retired_by_kind:
        for token in sorted(retired):
            match = re.fullmatch(r"[SPW](?P<number>\d+)(?:[a-z])?", token)
            if match is not None and len(match.group("number")) >= 2:
                continue
            findings.append(
                Finding(
                    code="PLAN020",
                    severity=Severity.ERROR,
                    message=(
                        f"Retirement ledger carries sub-canonical {kind} "
                        f"identifier '{token}'; canonical width is two "
                        "digits or more."
                    ),
                    line_number=0,
                    fix_hint=(
                        "Either widen the token in the hidden "
                        "<!-- RETIRED: ... --> ledger to canonical width "
                        "(e.g. 'S1' -> 'S01') or remove it entirely if "
                        "the corresponding live row never existed."
                    ),
                    autofixable=False,
                ),
            )
    return findings


def _detect_alpha_suffixes(source_text: str) -> list[Finding]:
    """Yield PLAN023 warnings for Wave / Phase alpha suffix identifiers."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for index, raw_line in enumerate(source_text.splitlines(), start=1):
        if not raw_line.startswith(("## Wave ", "### Phase ")):
            continue
        for match in _RE_ALPHA_SUFFIX_CONTAINER_ID.finditer(raw_line):
            token = match.group("token")
            if token in seen:
                continue
            seen.add(token)
            kind = "Wave" if token.startswith("W") else "Phase"
            suffix = token[-1]
            canonical = token[:-1] + suffix.lower()
            if suffix.islower():
                message = (
                    f"{kind} identifier '{token}' uses an alpha suffix for "
                    "stable insertion."
                )
                hint = (
                    "Alpha suffixes are supported for Wave and Phase ids only; "
                    "keep the suffix lowercase and do not use alpha suffixes "
                    "for Step ids."
                )
            else:
                message = (
                    f"{kind} identifier '{token}' uses an uppercase alpha suffix; "
                    f"canonical suffix form is '{canonical}'."
                )
                hint = (
                    "Canonicalise the suffix to lowercase. Alpha suffixes are "
                    "supported for Wave and Phase ids only."
                )
            findings.append(
                Finding(
                    code="PLAN023",
                    severity=Severity.WARNING,
                    message=message,
                    line_number=index,
                    fix_hint=hint,
                    autofixable=False,
                ),
            )
    return findings


def _detect_step_alpha_suffixes(source_text: str) -> list[Finding]:
    """Yield PLAN020 errors for alpha suffixes on Step identifiers."""
    findings: list[Finding] = []
    for index, raw_line in enumerate(source_text.splitlines(), start=1):
        if not raw_line.startswith("- ["):
            continue
        match = _RE_ALPHA_SUFFIX_STEP_ID.search(raw_line)
        if match is None:
            continue
        token = match.group("token")
        findings.append(
            Finding(
                code="PLAN020",
                severity=Severity.ERROR,
                message=(
                    f"Step identifier '{token}' uses an alpha suffix; "
                    "alpha suffixes are supported only for Wave and Phase ids."
                ),
                line_number=index,
                fix_hint=(
                    "Remove the Step suffix and allocate a numeric Step id "
                    "through 'vaultspec-core vault plan step add' or "
                    "'vaultspec-core vault plan step insert'."
                ),
                autofixable=False,
            ),
        )
    return findings


def _detect_underpadded_headings(source_text: str) -> list[Finding]:
    """Yield PLAN020 findings for single-digit Wave / Phase heading ids.

    The parser regex requires a ``\\d{2,}`` minimum and silently drops
    such headings; the rule scans the raw text so the violation is
    still surfaced to the writer.
    """
    findings: list[Finding] = []
    for index, raw_line in enumerate(source_text.splitlines(), start=1):
        match = _RE_UNDERPADDED_HEADING_ID.match(raw_line)
        if match is None:
            continue
        token = match.group("token")
        kind = "Wave" if token.startswith("W") else "Phase"
        findings.append(
            Finding(
                code="PLAN020",
                severity=Severity.ERROR,
                message=(
                    f"{kind} heading identifier '{token}' violates the "
                    "two-digit minimum padding rule and is silently "
                    "dropped by the parser."
                ),
                line_number=index,
                fix_hint=(
                    "Pad the numeric tail to at least two digits "
                    "(e.g. 'W1' -> 'W01'). Hand-edits to widen padding "
                    "are forbidden once a plan is in flight; "
                    "re-create the container via the appropriate "
                    "'vaultspec-core vault plan {wave|phase} add' command."
                ),
                autofixable=False,
            ),
        )
    return findings


def _detect_duplicates(
    identifiers: list[str],
    *,
    kind: str,
    line_lookup: list,
) -> list[Finding]:
    """Yield one Finding per duplicate canonical identifier."""
    counts: dict[str, list[int]] = {}
    for index, identifier in enumerate(identifiers):
        counts.setdefault(identifier, []).append(index)
    findings: list[Finding] = []
    for identifier, occurrences in counts.items():
        if len(occurrences) <= 1:
            continue
        first_line = line_lookup[occurrences[0]].line_number
        findings.append(
            Finding(
                code="PLAN021",
                severity=Severity.ERROR,
                message=(
                    f"{kind} canonical identifier '{identifier}' appears "
                    f"{len(occurrences)} times in document order."
                ),
                line_number=first_line,
                fix_hint=(
                    "Remove or rename the duplicate occurrences; the "
                    "convention forbids re-using retired identifiers."
                ),
                autofixable=False,
            ),
        )
    return findings


def _detect_non_monotonic(identifiers: list[str], *, kind: str) -> list[Finding]:
    """Yield one Finding when identifiers are not strictly increasing."""
    numbers = [int(identifier[1:]) for identifier in identifiers]
    sorted_numbers = sorted(numbers)
    if numbers != sorted_numbers:
        return [
            Finding(
                code="PLAN022",
                severity=Severity.WARNING,
                message=(
                    f"{kind} canonical identifiers are not strictly "
                    "monotonic in document order; an earlier row carries "
                    "a higher number than a later one."
                ),
                line_number=0,
                fix_hint=(
                    "Document order may diverge from canonical-id order "
                    "by design (insert-between scenarios). Verify this "
                    "ordering reflects writer intent rather than a "
                    "hand-edit error."
                ),
                autofixable=False,
            ),
        ]
    return []
