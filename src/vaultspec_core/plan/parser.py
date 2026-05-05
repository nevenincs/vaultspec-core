"""Plan-document hierarchy parser.

Walks a plan markdown body and builds the structured model
(:class:`Plan` -> :class:`Wave` -> :class:`Phase` -> :class:`Step`)
defined by the convention ADR's *Hierarchy and tiers* section.

The parser is **document-order preserving**: rows and containers appear
in the model in the order they appear in the file. Canonical
identifiers are extracted from the row prefix (e.g., ``S03``, ``P02.S03``,
``W01.P02.S03``); the leaf segment is treated as the canonical Step
identifier per the convention's *Identifiers and addressing* rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vaultspec_core.plan.frontmatter import (
    PlanFrontmatter,
    Tier,
    parse_plan_frontmatter,
)
from vaultspec_core.vaultcore.parser import parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "EpicIntent",
    "Phase",
    "Plan",
    "PlanParseError",
    "Step",
    "Wave",
    "parse_plan",
]


# ---- Model ------------------------------------------------------------------


@dataclass
class Step:
    """One Step row from the plan body.

    Attributes:
        canonical_id: The leaf segment of the display path (e.g., ``S03``).
            Unique per plan document; append-only and immutable.
        display_path: The rendered ancestor-aware path (e.g., ``W01.P02.S03``).
            Tier-conditional: at ``L1`` this equals the canonical id.
        checked: ``True`` when the checkbox state is ``[x]``.
        action: Imperative-verb action statement, without trailing scope.
        scope: File or area scope from the ``;`` clause (no surrounding backticks).
        raw_line: The original line as read from the document, including the
            leading ``-`` and trailing newline-stripped form.
        line_number: 1-based line number in the source document.
    """

    canonical_id: str
    display_path: str
    checked: bool
    action: str
    scope: str
    raw_line: str
    line_number: int


@dataclass
class Phase:
    """A Phase block: a heading, an intent paragraph, and contiguous Step rows.

    Attributes:
        canonical_id: ``P##`` segment from the heading's display path.
        display_path: Heading-rendered path (``P##`` at ``L2``;
            ``W##.P##`` at ``L3``/``L4``).
        title: Heading title text after the ``-`` separator.
        intent: One-paragraph intent text immediately following the heading.
        steps: Step rows in document order.
        line_number: Heading line number in the source document.
    """

    canonical_id: str
    display_path: str
    title: str
    intent: str
    steps: list[Step] = field(default_factory=list)
    line_number: int = 0


@dataclass
class Wave:
    """A Wave block (``L3``/``L4`` only): heading, intent paragraph, Phases.

    Attributes:
        canonical_id: ``W##`` identifier.
        title: Wave heading title.
        intent: Wave intent paragraph.
        phases: Phase blocks in document order.
        line_number: Heading line number.
    """

    canonical_id: str
    title: str
    intent: str
    phases: list[Phase] = field(default_factory=list)
    line_number: int = 0


@dataclass
class EpicIntent:
    """The ``## Epic intent`` block (``L4`` only).

    Attributes:
        text: The intent paragraph(s) following the heading.
        line_number: Heading line number.
    """

    text: str
    line_number: int = 0


@dataclass
class Plan:
    """Parsed plan-document model.

    The container fields are populated tier-conditionally:

    - ``L1``: ``steps`` holds the flat row list; ``phases``, ``waves``,
      ``epic_intent`` are empty / ``None``.
    - ``L2``: ``phases`` holds Phase blocks (each containing Steps);
      ``steps`` mirrors all Steps in document order for convenience.
    - ``L3``: ``waves`` holds Wave blocks; ``phases`` and ``steps`` mirror
      the flattened descendants.
    - ``L4``: same as ``L3`` plus ``epic_intent`` is non-``None``.

    Attributes:
        frontmatter: Validated frontmatter with the declared ``tier``.
        title: First-line ``# ...`` heading text after the frontmatter.
        epic_intent: The ``L4`` Epic intent block, or ``None`` at lower tiers.
        waves: Wave blocks at ``L3`` and ``L4``; empty otherwise.
        phases: Phase blocks at ``L2``, ``L3``, ``L4``; empty at ``L1``.
            For ``L3``/``L4`` plans, mirrors the flattened descendants of
            every Wave in document order.
        steps: All Step rows in document order, regardless of tier.
    """

    frontmatter: PlanFrontmatter
    title: str
    epic_intent: EpicIntent | None = None
    waves: list[Wave] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)


class PlanParseError(ValueError):
    """Raised when a plan document violates the hierarchy or row contract."""


# ---- Regexes (compiled once) -----------------------------------------------


_RE_TITLE = re.compile(r"^# +(?P<title>.+?)\s*$")
_RE_WAVE_HEADING = re.compile(
    r"^## +Wave +`(?P<id>W\d{2,})` *- *(?P<title>.+?)\s*$",
)
_RE_EPIC_INTENT = re.compile(r"^## +Epic intent\s*$")
_RE_PHASE_HEADING = re.compile(
    r"^### +Phase +`(?P<path>(?:W\d{2,}\.)?P\d{2,})` *- *(?P<title>.+?)\s*$",
)
_RE_STEP_ROW = re.compile(
    r"^- +\[(?P<state>[ x])\] +"
    r"`(?P<path>(?:W\d{2,}\.)?(?:P\d{2,}\.)?S\d{2,})` *- *"
    r"(?P<rest>.+?)\s*$",
)
_RE_FRONTMATTER_FENCE = re.compile(r"^---\s*$")


# ---- Public entry point -----------------------------------------------------


def parse_plan(source: str | Path) -> Plan:
    """Parse a plan document into a structured :class:`Plan` model.

    Args:
        source: Either the full markdown text of a plan document or a path
            to one. When a path is given, the file is read with UTF-8
            encoding.

    Returns:
        :class:`Plan` populated with frontmatter, title, optional Epic
        intent, and tier-appropriate container chains.

    Raises:
        PlanParseError: When a Step row violates the row contract, a
            heading is malformed, or the document structure is otherwise
            unparseable.
    """
    text = _coerce_to_text(source)
    frontmatter = parse_plan_frontmatter(text)
    _, body = parse_frontmatter(text)

    title = _extract_title(body)
    epic_intent = _extract_epic_intent(body)
    waves, phases, steps = _walk_body(body)

    return Plan(
        frontmatter=frontmatter,
        title=title,
        epic_intent=epic_intent,
        waves=waves,
        phases=phases,
        steps=steps,
    )


# ---- Internals --------------------------------------------------------------


def _coerce_to_text(source: str | Path) -> str:
    """Return raw markdown text from a string or path."""
    from pathlib import Path as _Path

    if isinstance(source, _Path):
        return source.read_text(encoding="utf-8")
    return source


def _extract_title(body: str) -> str:
    """Return the first ``# ...`` heading text in the body, or ``""`` if absent."""
    for line in body.splitlines():
        match = _RE_TITLE.match(line)
        if match:
            return match.group("title")
    return ""


def _extract_epic_intent(body: str) -> EpicIntent | None:
    """Return the ``## Epic intent`` block when present, ``None`` otherwise.

    The intent text spans every paragraph from the line after the heading
    until the next ``##``-or-greater heading.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if _RE_EPIC_INTENT.match(line):
            text_lines: list[str] = []
            for follow in lines[index + 1 :]:
                if follow.startswith("## ") or follow.startswith("# "):
                    break
                text_lines.append(follow)
            return EpicIntent(
                text="\n".join(text_lines).strip(),
                line_number=index + 1,
            )
    return None


def _walk_body(body: str) -> tuple[list[Wave], list[Phase], list[Step]]:
    """Walk the body line-by-line and assemble the container chains.

    Document-order is preserved: containers are appended as they are
    discovered. The returned ``phases`` and ``steps`` are flattened
    mirrors that convey order across the entire document.

    Intent prose between a Wave or Phase heading and the next
    structural element (row, sub-heading, or sibling heading) is
    captured into the corresponding container's ``intent`` field so
    that round-trips do not silently discard it.
    """
    waves: list[Wave] = []
    phases: list[Phase] = []
    steps: list[Step] = []

    current_wave: Wave | None = None
    current_phase: Phase | None = None
    intent_target: Wave | Phase | None = None
    intent_buffer: list[str] = []

    def _flush_intent() -> None:
        if intent_target is not None and intent_buffer:
            intent_target.intent = "\n".join(intent_buffer).strip()
        intent_buffer.clear()

    for index, line in enumerate(body.splitlines(), start=1):
        wave_match = _RE_WAVE_HEADING.match(line)
        phase_match = _RE_PHASE_HEADING.match(line)
        step_match = _RE_STEP_ROW.match(line)

        if wave_match:
            _flush_intent()
            current_wave = Wave(
                canonical_id=wave_match.group("id"),
                title=wave_match.group("title"),
                intent="",
                line_number=index,
            )
            waves.append(current_wave)
            current_phase = None
            intent_target = current_wave
            continue

        if phase_match:
            _flush_intent()
            path = phase_match.group("path")
            phase_id = path.split(".")[-1]
            current_phase = Phase(
                canonical_id=phase_id,
                display_path=path,
                title=phase_match.group("title"),
                intent="",
                line_number=index,
            )
            phases.append(current_phase)
            if current_wave is not None:
                current_wave.phases.append(current_phase)
            intent_target = current_phase
            continue

        if step_match:
            _flush_intent()
            intent_target = None
            step = _build_step(step_match, index, line)
            steps.append(step)
            if current_phase is not None:
                current_phase.steps.append(step)
            continue

        if intent_target is not None:
            stripped = line.strip()
            if stripped.startswith("# ") or stripped.startswith("## "):
                _flush_intent()
                intent_target = None
                continue
            intent_buffer.append(line)

    _flush_intent()

    return waves, phases, steps


def _build_step(match: re.Match[str], index: int, raw_line: str) -> Step:
    """Construct a :class:`Step` from a row-match plus metadata."""
    rest = match.group("rest")
    action, scope = _split_action_and_scope(rest)
    path = match.group("path")
    canonical_id = path.split(".")[-1]
    return Step(
        canonical_id=canonical_id,
        display_path=path,
        checked=match.group("state") == "x",
        action=action,
        scope=scope,
        raw_line=raw_line,
        line_number=index,
    )


def _split_action_and_scope(rest: str) -> tuple[str, str]:
    """Split a row's tail into the imperative action and the file/area scope.

    The convention's row contract uses ``;`` to separate the action from
    the scope, with a trailing period after the scope's closing backtick.
    """
    rest = rest.rstrip(".").rstrip()
    if ";" not in rest:
        raise PlanParseError(
            f"Step row missing ';' separator between action and scope: {rest!r}",
        )
    action_part, scope_part = rest.split(";", maxsplit=1)
    scope = scope_part.strip().strip("`")
    return action_part.strip(), scope


def _is_l4_with_intent(frontmatter: PlanFrontmatter) -> bool:
    """Return ``True`` when the plan is ``L4`` (Epic intent expected)."""
    return frontmatter.tier is Tier.L4
