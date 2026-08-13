"""Integrity guards for serialised plan writes, shared by every write path.

Five defensive checks protect a plan document across the moment its mutated,
re-serialised text replaces the on-disk bytes, and they must run on *every*
write path so no surface can corrupt a plan the others protect. Two run
*before* the write:

- **Unexpected-retirement guard** (issue #150): a legitimate mutation retires
  only the canonical identifiers the operation intends to retire. Any identifier
  that becomes retired beyond that expected set signals a serialisation conflict
  that would silently drop live plan items, so the write is refused. This is the
  guard that protects canonical-identifier and gap-no-reuse integrity, so it is
  shared rather than owned by the CLI alone.
- **Growth-ceiling guard** (issue #125): a single structural edit never
  multiplies a plan several times over, so serialised output larger than
  ``max(floor, factor * len(source))`` signals a serialiser fault and the write
  is refused rather than corrupting the file or exhausting the disk.
- **Source-structure guard** (issue #305): a plan with error-level structural
  findings is not safe input to a whole-document rewrite. The mutation is
  refused with the checker's existing diagnosis and repair hint.
- **Active-identifier preservation guard** (issue #305): every Wave, Phase,
  and Step visible before a mutation must remain visible afterwards unless the
  command explicitly retires it. This catches destructive round trips even
  when no individual checker recognises the malformed input that caused them.

One runs *after* the write:

- **Write-verification guard** (issue #296): a plan verb must never report a
  success-shaped outcome for a mutation the document did not actually receive.
  :func:`verify_plan_write` re-reads the persisted bytes, re-parses them, and
  asserts the document still carries exactly the containers and rows - with
  exactly the canonical identifiers - the mutated model intended. A divergence
  is a hard, typed failure rather than a silent wrong state that only an
  independent re-read of the file would reveal.

Both the CLI plan-mutation verbs and the MCP ``plan_edit`` / ``plan_progress``
tools serialise a mutated plan and write it back; routing both through
:func:`guard_plan_write` and :func:`verify_plan_write` guarantees the MCP
surface inherits exactly the integrity the CLI enforces, with no second copy of
the check to drift.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from vaultspec_core.plan.commands._errors import PlanCommandError

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.plan.parser import Phase, Plan, Step

__all__ = [
    "PlanWriteGuardError",
    "PlanWriteVerificationError",
    "guard_plan_write",
    "verify_plan_write",
]

#: Byte floor below which the growth ceiling never trips, so tiny plans stay
#: editable even when a single edit more than quadruples their size.
_PLAN_GROWTH_FLOOR = 65_536

#: Multiplier applied to the source length to derive the growth ceiling.
_PLAN_GROWTH_FACTOR = 4


class PlanWriteGuardError(PlanCommandError):
    """A serialised plan write was refused by an integrity guard.

    Subclasses :class:`~vaultspec_core.plan.commands._errors.PlanCommandError`
    so the CLI's ``render_user_errors`` decorator renders it as a one-line
    error exactly as before the extraction, while the MCP tool handlers surface
    it as a protocol ``isError`` result like any other whole-call failure.
    """


class PlanWriteVerificationError(PlanWriteGuardError):
    """A persisted plan write did not carry the mutation that produced it.

    Raised by :func:`verify_plan_write` when the document re-read from disk
    does not match the text the verb serialised, no longer parses, or parses
    into a different set of containers and rows than the mutated model held.
    Subclasses :class:`PlanWriteGuardError` so every surface that already
    renders a refused write renders a failed verification the same way; the
    distinct type lets a caller tell "refused before writing" from "wrote
    something other than what was asked".
    """


def _retired_ids(plan: Plan) -> set[str]:
    """Return the union of a plan's retired step, phase, and wave identifiers."""
    return plan.retired_step_ids | plan.retired_phase_ids | plan.retired_wave_ids


def _active_ids(plan: Plan) -> Counter[str]:
    """Return multiplicity-aware active container and Step identifiers."""
    return Counter(
        [wave.canonical_id for wave in plan.waves]
        + [phase.canonical_id for phase in plan.phases]
        + [step.canonical_id for step in plan.steps]
    )


def _guard_source_structure(plan: Plan, source_text: str) -> None:
    """Refuse a whole-document rewrite of structurally invalid source."""
    from vaultspec_core.plan.checks import Severity, collect_all

    destructive_structure_codes = {"PLAN010", "PLAN070"}
    errors = [
        finding
        for finding in collect_all(plan, source_text)
        if finding.severity is Severity.ERROR
        and finding.code in destructive_structure_codes
    ]
    if not errors:
        return

    details = "; ".join(
        f"{finding.code} line {finding.line_number}: {finding.message} "
        f"Fix: {finding.fix_hint}"
        for finding in errors
    )
    raise PlanWriteGuardError(
        "mutation aborted: the source plan has structural errors and is not "
        f"safe to rewrite. {details}"
    )


def guard_plan_write(
    original_text: str,
    new_text: str,
    expected_retired: set[str] | None,
    *,
    path_name: str,
) -> None:
    """Run both plan-write integrity guards over a pending serialisation.

    Parses the pre- and post-mutation text once, then enforces the source
    structure, unexpected-retirement, active-identifier preservation, and
    growth-ceiling guards in that order. A parse
    failure on either text is itself a refusal, since an unparseable result is
    never a safe thing to persist.

    Args:
        original_text: The plan document's pre-mutation text.
        new_text: The serialised, stamp-refreshed text about to be written.
        expected_retired: The canonical identifiers the mutation legitimately
            retires (empty or ``None`` for a mutation that retires nothing).
        path_name: The plan filename, used only in the growth-ceiling message.

    Raises:
        PlanWriteGuardError: When the mutated text fails to parse, retires an
            identifier outside *expected_retired*, or exceeds the growth ceiling.
    """
    from vaultspec_core.plan.parser import parse_plan

    try:
        old_plan = parse_plan(original_text)
        new_plan = parse_plan(new_text)
    except Exception as exc:  # any parse failure is itself a refusal
        msg = f"Plan validation failed during parsing: {exc}"
        raise PlanWriteGuardError(msg) from exc

    _guard_source_structure(old_plan, original_text)

    newly_retired = _retired_ids(new_plan) - _retired_ids(old_plan)
    expected: set[str] = expected_retired if expected_retired is not None else set()
    unexpected = newly_retired - expected
    if unexpected:
        joined = ", ".join(sorted(unexpected))
        msg = (
            f"mutation aborted: unexpected retirement of active plan items: "
            f"{joined}. This indicates a serialization conflict."
        )
        raise PlanWriteGuardError(msg)

    lost_active = _active_ids(old_plan) - _active_ids(new_plan)
    for identifier in expected:
        del lost_active[identifier]
    if lost_active:
        joined = ", ".join(
            f"{identifier} ({count} occurrence(s))"
            for identifier, count in sorted(lost_active.items())
        )
        msg = (
            "mutation aborted: serialised output drops active plan items: "
            f"{joined}. No write was performed; repair the source structure "
            "and retry."
        )
        raise PlanWriteGuardError(msg)

    growth_ceiling = max(_PLAN_GROWTH_FLOOR, _PLAN_GROWTH_FACTOR * len(original_text))
    if len(new_text) > growth_ceiling:
        msg = (
            f"refusing to write {path_name}: serialised output "
            f"({len(new_text)} bytes) is implausibly larger than the source "
            f"({len(original_text)} bytes); this indicates a serialiser fault, "
            "not an intended edit. The file on disk was left unchanged."
        )
        raise PlanWriteGuardError(msg)


def verify_plan_write(path: Path, expected_text: str, expected_plan: Plan) -> None:
    """Re-read a just-written plan and prove it carries the intended mutation.

    Every plan-mutation verb owns the canonical-identifier guarantee the
    project's mandate rests on, so a verb must never report success for a
    change the document did not receive. Under concurrency a write can land
    partially, be clobbered by another writer, or - through a serialise /
    re-parse round trip that loses information - persist text that means
    something other than what was asked. Each of those leaves a wrong state
    indistinguishable from the right one unless the file is independently
    re-read, which is exactly what this function does (issue #296).

    Three assertions run in order, each strictly stronger than a bare
    "the call returned":

    1. The bytes on disk are byte-identical to the serialised text the verb
       intended to persist.
    2. Those bytes still parse as a plan.
    3. The re-parsed document holds the same ordered containers and rows -
       with the same canonical identifiers, titles, checkbox states, actions,
       and scopes - as the mutated model, and the same retirement ledger.

    Assertion 3 is not implied by assertion 1: the serialiser is only the
    parser's inverse for content that round-trips, so text that matches
    byte-for-byte can still re-parse into a different structure. That is the
    arm that catches a Phase heading or Step row silently landing with content
    other than the one requested.

    Assertion 1 compares decoded text, not raw bytes, so it is deliberately
    blind to the newline convention a platform's text layer may have applied
    on the way out: a differing line terminator is a formatting question the
    document conventions own, not evidence that the mutation was lost.

    Args:
        path: The plan document that was just written.
        expected_text: The serialised, stamp-refreshed text the verb wrote.
        expected_plan: The mutated :class:`~vaultspec_core.plan.parser.Plan`
            model that *expected_text* was serialised from.

    Raises:
        PlanWriteVerificationError: When the document cannot be re-read, its
            bytes differ from *expected_text*, it no longer parses, or it
            parses into a structure other than *expected_plan*'s.
    """
    from vaultspec_core.plan.parser import parse_plan

    try:
        observed_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        msg = (
            f"write verification failed for {path.name}: the document could "
            f"not be re-read after the mutation ({exc}). The plan is in an "
            "unknown state on disk; re-read it before trusting any verb output."
        )
        raise PlanWriteVerificationError(msg) from exc

    if observed_text != expected_text:
        msg = (
            f"write verification failed for {path.name}: the document on disk "
            f"({len(observed_text)} chars) does not match the text this "
            f"mutation wrote ({len(expected_text)} chars); they first diverge "
            f"at offset {_first_divergence(expected_text, observed_text)}. The "
            "write did not land as issued - a concurrent writer or a partial "
            "write is the likely cause. Re-read the document and re-apply."
        )
        raise PlanWriteVerificationError(msg)

    try:
        observed_plan = parse_plan(observed_text)
    except Exception as exc:
        msg = (
            f"write verification failed for {path.name}: the persisted "
            f"document no longer parses as a plan ({exc})."
        )
        raise PlanWriteVerificationError(msg) from exc

    expected_rows = _document_rows(expected_plan)
    observed_rows = _document_rows(observed_plan)
    if expected_rows != observed_rows:
        msg = (
            f"write verification failed for {path.name}: the persisted "
            f"document does not carry the mutation that was applied - "
            f"{_describe_row_divergence(expected_rows, observed_rows)}. The "
            "serialised row did not survive the round trip, so the verb's "
            "result would have described a change the document does not hold."
        )
        raise PlanWriteVerificationError(msg)

    if _retired_ids(expected_plan) != _retired_ids(observed_plan):
        expected_only = _retired_ids(expected_plan) - _retired_ids(observed_plan)
        observed_only = _retired_ids(observed_plan) - _retired_ids(expected_plan)
        msg = (
            f"write verification failed for {path.name}: the persisted "
            f"retirement ledger diverges from the mutation - missing "
            f"{sorted(expected_only) or 'nothing'}, unexpected "
            f"{sorted(observed_only) or 'nothing'}. Retired canonical "
            "identifiers must never be lost or invented by a write."
        )
        raise PlanWriteVerificationError(msg)


def _first_divergence(expected: str, observed: str) -> int:
    """Return the first index at which two texts differ.

    When one text is a prefix of the other the shorter length is the
    divergence point, so a truncated write reports where it stopped.
    """
    limit = min(len(expected), len(observed))
    for index in range(limit):
        if expected[index] != observed[index]:
            return index
    return limit


def _normalise_row_text(value: str) -> str:
    """Return *value* under the normalisation a Step row round trip applies.

    The row contract owns its own delimiters, so
    :func:`~vaultspec_core.plan.parser.parse_plan` strips surrounding
    whitespace and the scope clause's backticks when it reads a row back.
    Applying the same normalisation to the intended text keeps verification
    focused on content the write genuinely lost, rather than firing on a
    caller who wrapped a scope in the backticks the serialiser adds anyway.
    """
    return value.strip().strip("`").strip()


def _step_row(step: Step) -> tuple[str, ...]:
    """Return the comparable identity of one Step row.

    ``display_path`` is deliberately excluded: the serialiser recomputes it
    from the live ancestor chain, so it carries no information the container
    walk does not already assert.
    """
    return (
        "step",
        step.canonical_id,
        "x" if step.checked else " ",
        _normalise_row_text(step.action),
        _normalise_row_text(step.scope),
    )


def _document_rows(plan: Plan) -> list[tuple[str, ...]]:
    """Flatten *plan* into the ordered rows the serialiser emits for its tier.

    The walk mirrors :func:`~vaultspec_core.plan.serialiser.serialise_plan`
    exactly - ``L1`` emits the flat Step list, ``L2`` walks Phases, ``L3`` and
    ``L4`` walk Waves then Phases - so a comparison against the re-parsed
    document is a true intent-versus-disk check rather than an artefact of the
    model's flat Step mirror, whose order may legitimately differ from
    document order after a mid-document insertion.

    Container intent paragraphs are excluded: the serialiser substitutes a
    placeholder for a container parsed without one, which is a documented
    normalisation rather than a lost mutation.
    """
    from vaultspec_core.plan.frontmatter import Tier

    tier = plan.frontmatter.tier
    if tier is Tier.L1:
        return [_step_row(step) for step in plan.steps]

    rows: list[tuple[str, ...]] = []
    if tier is Tier.L2:
        for phase in plan.phases:
            rows.extend(_phase_rows(phase))
        return rows

    for wave in plan.waves:
        rows.append(("wave", wave.canonical_id, _normalise_row_text(wave.title)))
        for phase in wave.phases:
            rows.extend(_phase_rows(phase))
    return rows


def _phase_rows(phase: Phase) -> list[tuple[str, ...]]:
    """Return the Phase heading row followed by its Step rows, in order."""
    rows: list[tuple[str, ...]] = [
        ("phase", phase.canonical_id, _normalise_row_text(phase.title))
    ]
    rows.extend(_step_row(step) for step in phase.steps)
    return rows


def _describe_row_divergence(
    expected: list[tuple[str, ...]],
    observed: list[tuple[str, ...]],
) -> str:
    """Summarise the first structural difference between two row walks."""
    for index in range(min(len(expected), len(observed))):
        if expected[index] != observed[index]:
            return (
                f"row {index} was written as {expected[index]!r} but reads "
                f"back as {observed[index]!r}"
            )
    if len(expected) > len(observed):
        return (
            f"{len(expected) - len(observed)} row(s) are missing, starting "
            f"with {expected[len(observed)]!r}"
        )
    return (
        f"{len(observed) - len(expected)} unexpected row(s) are present, "
        f"starting with {observed[len(expected)]!r}"
    )
