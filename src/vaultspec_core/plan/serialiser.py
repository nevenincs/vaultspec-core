"""Plan model -> Markdown emitter.

Emits a parsed :class:`Plan` back to canonical Markdown text. The
emitter preserves document order (Steps appear in the same sequence
the model holds them), recomputes display paths from the current
ancestor chain, and renders frontmatter in the convention's YAML
style: single-quoted string scalars, unquoted ``tier`` enum, list
form for ``related`` and ``tags``.

The serialiser is the inverse of :func:`vaultspec_core.plan.parser.parse_plan`
for clean plans; the round-trip ``parse -> serialise -> parse`` yields
an equivalent model. Byte-stability across round-trips is **not**
guaranteed when the source document carried non-canonical formatting
(extra blank lines, atypical YAML quoting); the emitter always writes
the canonical form.
"""

from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING

from vaultspec_core.plan.display_path import (
    phase_display_path,
    step_display_path,
    wave_display_path,
)
from vaultspec_core.plan.frontmatter import Tier

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Phase, Plan, Step, Wave

__all__ = ["serialise_plan"]


class _UnknownBlockConsumer:
    """Document-order, single-consume view over a plan's unknown blocks.

    The parser anchors authored prose to the *bare* leaf identifier of the
    container it precedes (e.g. ``before_step_S01``), and per-phase Step
    numbering means an id such as ``S01`` recurs in every phase. A naive
    serialiser that re-scans the global ``plan.unknown_blocks`` list for
    each container therefore re-emits a colliding block once per occurrence;
    the duplicated prose then merges on the next parse and multiplies again,
    growing the serialised text exponentially across round-trips until the
    file corrupts the workspace (see issue #125).

    This consumer removes that failure mode structurally. Blocks are bucketed
    into per-anchor FIFO queues in document order and each is handed out at
    most once. Because the serialiser visits anchor slots in the same
    document order the parser recorded them, every block binds to exactly one
    location and a clean ``parse -> serialise`` round-trip is byte-stable.
    """

    def __init__(self, plan: Plan, *, enabled: bool) -> None:
        self._contents: list[str] = [b.content for b in plan.unknown_blocks]
        self._pending: dict[str, deque[int]] = {}
        self._consumed: set[int] = set()
        self._enabled = enabled
        if enabled:
            for index, block in enumerate(plan.unknown_blocks):
                self._pending.setdefault(block.anchor, deque()).append(index)

    def take(self, anchor: str) -> str | None:
        """Return the next unconsumed block for ``anchor``, or ``None``."""
        queue = self._pending.get(anchor)
        if not queue:
            return None
        index = queue.popleft()
        self._consumed.add(index)
        return self._contents[index]

    def leftovers(self) -> list[str]:
        """Return blocks never consumed, in document order.

        A block goes unconsumed only when its anchor slot no longer exists in
        the model (e.g. the container it preceded was removed by a CLI edit).
        Emitting these at the document tail preserves authored prose rather
        than silently dropping it.
        """
        if not self._enabled:
            return []
        return [
            self._contents[index]
            for index in range(len(self._contents))
            if index not in self._consumed
        ]


def serialise_plan(plan: Plan, canonicalise: bool = False) -> str:
    """Return canonical Markdown text for ``plan``.

    Args:
        plan: Parsed :class:`Plan` model.
        canonicalise: If True, do not preserve unknown blocks.

    Returns:
        Markdown text terminated by a single trailing newline.
    """
    consumer = _UnknownBlockConsumer(plan, enabled=not canonicalise)

    parts: list[str] = []
    parts.append(_render_frontmatter(plan))
    parts.append("")
    parts.append(_render_link_rules_comment())
    parts.append("")
    ledger = _render_retirement_ledger(plan)
    if ledger is not None:
        parts.append(ledger)
        parts.append("")

    _emit_block(parts, consumer.take("before_title"))

    parts.append(f"# {plan.title or '(untitled plan)'}")
    parts.append("")

    _emit_block(parts, consumer.take("before_epic_intent"))

    if plan.frontmatter.tier is Tier.L4 and plan.epic_intent is not None:
        parts.append("## Epic intent")
        parts.append("")
        parts.append(plan.epic_intent.text)
        parts.append("")

    if plan.frontmatter.tier is Tier.L1:
        for step in plan.steps:
            _emit_block(parts, consumer.take(f"before_step_{step.canonical_id}"))
            parts.append(_render_step_row(step, phase_id=None, wave_id=None))
    elif plan.frontmatter.tier is Tier.L2:
        for phase in plan.phases:
            parts.extend(_render_phase_block(phase, wave_id=None, consumer=consumer))
    else:
        for wave in plan.waves:
            parts.extend(_render_wave_block(wave, consumer=consumer))

    _emit_block(parts, consumer.take("after_all"))

    # Any block whose anchor slot vanished (e.g. its container was removed by
    # a CLI edit) is preserved at the tail rather than silently dropped.
    for content in consumer.leftovers():
        _emit_block(parts, content)

    return "\n".join(parts).rstrip() + "\n"


def _emit_block(parts: list[str], content: str | None) -> None:
    """Append an unknown-block ``content`` plus a trailing blank line, if any."""
    if content is not None:
        parts.append(content)
        parts.append("")


def _render_frontmatter(plan: Plan) -> str:
    fm = plan.frontmatter
    lines = ["---", "tags:"]
    for tag in fm.tags:
        lines.append(f"  - '{tag}'")
    lines.append(f"date: '{fm.date}'")
    lines.append(f"tier: {fm.tier.value}")
    if fm.related:
        lines.append("related:")
        for entry in fm.related:
            lines.append(f"  - '{entry}'")
    lines.append("---")
    return "\n".join(lines)


def _render_link_rules_comment() -> str:
    lines = [
        "<!-- LINK RULES:",
        "     - [[wiki-links]] are ONLY for .vault/ documents in the",
        "       related: field above.",
        "     - The related: field carries the AUTHORISING documents",
        "       (ADR, research, reference, prior plan) for every Step in",
        "       this plan. Steps inherit this chain; per-row reference",
        "       footers do not exist.",
        "     - NEVER use [[wiki-links]] or markdown links in the",
        "       document body. -->",
    ]
    return "\n".join(lines)


def _render_step_row(
    step: Step,
    *,
    phase_id: str | None,
    wave_id: str | None,
) -> str:
    state = "x" if step.checked else " "
    path = step_display_path(
        step_id=step.canonical_id,
        phase_id=phase_id,
        wave_id=wave_id,
    )
    return f"- [{state}] `{path}` - {step.action}; `{step.scope}`."


def _render_phase_block(
    phase: Phase,
    *,
    wave_id: str | None,
    consumer: _UnknownBlockConsumer,
) -> list[str]:
    path = phase_display_path(phase_id=phase.canonical_id, wave_id=wave_id)
    lines: list[str] = []

    _emit_block(lines, consumer.take(f"before_phase_{phase.canonical_id}"))

    lines.extend(
        [
            f"### Phase `{path}` - {phase.title}",
            "",
            phase.intent or _placeholder_intent("Phase"),
            "",
        ]
    )

    for step in phase.steps:
        _emit_block(lines, consumer.take(f"before_step_{step.canonical_id}"))
        lines.append(
            _render_step_row(step, phase_id=phase.canonical_id, wave_id=wave_id),
        )
    lines.append("")
    return lines


def _render_wave_block(wave: Wave, *, consumer: _UnknownBlockConsumer) -> list[str]:
    path = wave_display_path(wave_id=wave.canonical_id)
    lines: list[str] = []

    _emit_block(lines, consumer.take(f"before_wave_{wave.canonical_id}"))

    lines.extend(
        [
            f"## Wave `{path}` - {wave.title}",
            "",
            wave.intent or _placeholder_intent("Wave"),
            "",
        ]
    )

    for phase in wave.phases:
        lines.extend(
            _render_phase_block(
                phase,
                wave_id=wave.canonical_id,
                consumer=consumer,
            )
        )
    return lines


def _render_retirement_ledger(plan: Plan) -> str | None:
    """Render the hidden HTML comment ledger of retired canonical ids.

    Emits ``<!-- RETIRED: <ids> -->`` when the plan has any retired
    Step / Phase / Wave identifiers; returns ``None`` when nothing has
    been retired so clean plans round-trip without an empty ledger.
    Tokens are sorted by container kind (Wave > Phase > Step) and then
    by numeric suffix so the output is deterministic.

    Position is canonical, not preserved: the ledger is always emitted
    immediately above the title heading, regardless of where the source
    document carried it. Multiple ledger comments in the source are
    unioned by the parser and emitted as a single canonical block.
    """
    tokens: list[str] = []
    retirement_sets = (
        plan.retired_wave_ids,
        plan.retired_phase_ids,
        plan.retired_step_ids,
    )
    for retired in retirement_sets:
        tokens.extend(sorted(retired, key=_retired_sort_key))
    if not tokens:
        return None
    return f"<!-- RETIRED: {', '.join(tokens)} -->"


def _retired_sort_key(identifier: str) -> tuple[int, int, str]:
    """Sort retired ids by numeric base, then optional alpha suffix."""
    match = re.fullmatch(
        r"(?P<kind>[SPW])(?P<number>\d+)(?P<suffix>[a-z]?)",
        identifier,
    )
    if match is None:
        return (10**9, 10**9, identifier)
    return (int(match.group("number")), ord(match.group("suffix") or "`"), identifier)


def _placeholder_intent(container: str) -> str:
    """Emit a placeholder intent paragraph for containers parsed without one.

    The convention requires an intent paragraph on every Phase and
    Wave; if the source document lacked one, the round-trip emits a
    minimal placeholder so downstream `vaultspec-core vault plan check` flags it as
    an authorial gap rather than silently swallowing the missing prose.
    """
    return f"TODO: {container} intent paragraph required by the convention ADR."
