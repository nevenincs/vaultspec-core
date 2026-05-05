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


def serialise_plan(plan: Plan) -> str:
    """Return canonical Markdown text for ``plan``.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        Markdown text terminated by a single trailing newline.
    """
    parts: list[str] = []
    parts.append(_render_frontmatter(plan))
    parts.append("")
    parts.append(_render_link_rules_comment())
    parts.append("")
    parts.append(f"# {plan.title}")
    parts.append("")

    if plan.frontmatter.tier is Tier.L4 and plan.epic_intent is not None:
        parts.append("## Epic intent")
        parts.append("")
        parts.append(plan.epic_intent.text)
        parts.append("")

    if plan.frontmatter.tier is Tier.L1:
        for step in plan.steps:
            parts.append(_render_step_row(step, phase_id=None, wave_id=None))
    elif plan.frontmatter.tier is Tier.L2:
        for phase in plan.phases:
            parts.extend(_render_phase_block(phase, wave_id=None))
    else:
        for wave in plan.waves:
            parts.extend(_render_wave_block(wave))

    return "\n".join(parts).rstrip() + "\n"


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


def _render_phase_block(phase: Phase, *, wave_id: str | None) -> list[str]:
    path = phase_display_path(phase_id=phase.canonical_id, wave_id=wave_id)
    lines = [
        f"### Phase `{path}` - {phase.title}",
        "",
        phase.intent or _placeholder_intent("Phase"),
        "",
    ]
    for step in phase.steps:
        lines.append(
            _render_step_row(step, phase_id=phase.canonical_id, wave_id=wave_id),
        )
    lines.append("")
    return lines


def _render_wave_block(wave: Wave) -> list[str]:
    path = wave_display_path(wave_id=wave.canonical_id)
    lines = [
        f"## Wave `{path}` - {wave.title}",
        "",
        wave.intent or _placeholder_intent("Wave"),
        "",
    ]
    for phase in wave.phases:
        lines.extend(_render_phase_block(phase, wave_id=wave.canonical_id))
    return lines


def _placeholder_intent(container: str) -> str:
    """Emit a placeholder intent paragraph for containers parsed without one.

    The convention requires an intent paragraph on every Phase and
    Wave; if the source document lacked one, the round-trip emits a
    minimal placeholder so downstream `vault plan check` flags it as
    an authorial gap rather than silently swallowing the missing prose.
    """
    return f"TODO: {container} intent paragraph required by the convention ADR."
