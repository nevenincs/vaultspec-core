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
from typing import TYPE_CHECKING, NamedTuple

from vaultspec_core.plan.frontmatter import (
    PlanFrontmatter,
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
    "UnknownBlock",
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
class UnknownBlock:
    """An unrecognized prose block from the plan document body.

    Attributes:
        anchor: Positioning anchor string.
        content: Verbatim content string.
    """

    anchor: str
    content: str


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
        retired_step_ids: Canonical Step ids previously created and then
            removed; the next-available counter must skip these. Persisted
            via a hidden HTML comment ledger so retirement survives
            parse / serialise round-trips.
        retired_phase_ids: Canonical Phase ids retired via remove or
            demote; same persistence as ``retired_step_ids``.
        retired_wave_ids: Canonical Wave ids retired via remove or
            demote; same persistence as ``retired_step_ids``.
        has_link_rules: Whether the source carried the generated ``LINK RULES``
            guidance block. Structural mutations preserve its absence after an
            explicit annotation sanitation pass.
    """

    frontmatter: PlanFrontmatter
    title: str
    epic_intent: EpicIntent | None = None
    waves: list[Wave] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    retired_step_ids: set[str] = field(default_factory=set)
    retired_phase_ids: set[str] = field(default_factory=set)
    retired_wave_ids: set[str] = field(default_factory=set)
    unknown_blocks: list[UnknownBlock] = field(default_factory=list)
    has_link_rules: bool = True


class PlanParseError(ValueError):
    """Raised when a plan document violates the hierarchy or row contract."""


# ---- Regexes (compiled once) -----------------------------------------------


_RE_TITLE = re.compile(r"^# +(?P<title>.+?)\s*$")
_RE_WAVE_HEADING = re.compile(
    r"^## +Wave +`(?P<id>W\d{2,}[a-z]?)` *- *(?P<title>.+?)\s*$",
)
_RE_EPIC_INTENT = re.compile(r"^## +Epic intent\s*$")
#: The section heading that opens a plan's container content. It is a
#: *structural* token, not authored prose: the serialiser owns it and
#: re-emits it unconditionally, so the parser consumes it here rather than
#: buffering it as an unknown block. Buffering it would stack a second copy
#: on the next round trip.
_RE_STEPS_HEADING = re.compile(r"^## +Steps\s*$")
_RE_PHASE_HEADING = re.compile(
    r"^### +Phase +`(?P<path>(?:W\d{2,}[a-z]?\.)?"
    r"P\d{2,}[a-z]?)` *- *(?P<title>.+?)\s*$",
)
_RE_STEP_ROW = re.compile(
    r"^- +\[(?P<state>[ x])\] +"
    r"`(?P<path>(?:W\d{2,}[a-z]?\.)?(?:P\d{2,}[a-z]?\.)?S\d{2,})` *- *"
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
    waves, phases, steps, unknown_blocks, has_link_rules = _walk_body(body)
    retired_steps, retired_phases, retired_waves = _extract_retirement_ledger(body)

    return Plan(
        frontmatter=frontmatter,
        title=title,
        epic_intent=epic_intent,
        waves=waves,
        phases=phases,
        steps=steps,
        retired_step_ids=retired_steps,
        retired_phase_ids=retired_phases,
        retired_wave_ids=retired_waves,
        unknown_blocks=unknown_blocks,
        has_link_rules=has_link_rules,
    )


_RE_RETIRED_LEDGER = re.compile(
    r"<!--\s*RETIRED:\s*(?P<body>[^>]*?)\s*-->",
)


def _extract_retirement_ledger(body: str) -> tuple[set[str], set[str], set[str]]:
    """Read retired canonical-id sets from the hidden ledger comment.

    The ledger has the form
    ``<!-- RETIRED: S04, S07, P02, W01 -->`` and may appear anywhere in
    the document body. Multiple occurrences are unioned. Tokens are
    captured under the lenient ``[SPW]\\d+`` shape so a sub-canonical
    width (e.g. ``S1``) survives parsing; the identifier-hygiene rule
    flags such tokens via PLAN020 rather than letting them be silently
    dropped from retirement tracking.

    Token matching is case-sensitive: ``s04`` / ``p02`` / ``w01`` do
    not match the token regexes and are silently ignored. The ledger
    schema is uppercase by spec; lower-cased tokens indicate hand-edit
    drift that should be repaired by canonicalising before commit.
    """
    retired_steps: set[str] = set()
    retired_phases: set[str] = set()
    retired_waves: set[str] = set()
    for match in _RE_RETIRED_LEDGER.finditer(body):
        for token in match.group("body").split(","):
            token = token.strip()
            if not token:
                continue
            if re.fullmatch(r"S\d+", token):
                retired_steps.add(token)
            elif re.fullmatch(r"P\d+[a-z]?", token):
                retired_phases.add(token)
            elif re.fullmatch(r"W\d+[a-z]?", token):
                retired_waves.add(token)
    return retired_steps, retired_phases, retired_waves


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
    until the next ``##``-or-greater heading. The hidden retirement-ledger
    comment is filtered out so it is not absorbed into authored prose.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if _RE_EPIC_INTENT.match(line):
            text_lines: list[str] = []
            for follow in lines[index + 1 :]:
                if (
                    follow.startswith("# ")
                    or follow.startswith("## ")
                    or follow.startswith("### ")
                ):
                    break
                if _RE_RETIRED_LEDGER.search(follow):
                    continue
                text_lines.append(follow)
            return EpicIntent(
                text="\n".join(text_lines).strip(),
                line_number=index + 1,
            )
    return None


class _LineTokens(NamedTuple):
    """Every structural token a single body line may match.

    Matching all six patterns once per line keeps the walk's branches
    reading against one immutable snapshot, rather than re-running
    regexes as each branch needs them.

    Attributes:
        title: The ``# ...`` document title match, if any.
        wave: The ``## Wave`` heading match, if any.
        phase: The ``### Phase`` heading match, if any.
        step: The Step row match, if any.
        epic_intent: The ``## Epic intent`` heading match, if any.
        steps_heading: The ``## Steps`` section heading match, if any.
    """

    title: re.Match[str] | None
    wave: re.Match[str] | None
    phase: re.Match[str] | None
    step: re.Match[str] | None
    epic_intent: re.Match[str] | None
    steps_heading: re.Match[str] | None

    def opens_a_structural_block(self) -> bool:
        """Return whether this line ends an open Epic intent paragraph.

        The Epic intent runs until the next structural token. ``## Steps``
        counts: a document that carries the section heading below its Epic
        intent would otherwise have the heading, and every line after it,
        swallowed into the intent text.
        """
        return bool(
            self.title or self.wave or self.phase or self.step or self.steps_heading
        )


def _match_line(line: str) -> _LineTokens:
    """Return every structural token *line* matches."""
    return _LineTokens(
        title=_RE_TITLE.match(line),
        wave=_RE_WAVE_HEADING.match(line),
        phase=_RE_PHASE_HEADING.match(line),
        step=_RE_STEP_ROW.match(line),
        epic_intent=_RE_EPIC_INTENT.match(line),
        steps_heading=_RE_STEPS_HEADING.match(line),
    )


def _build_wave(match: re.Match[str], index: int) -> Wave:
    """Construct a :class:`Wave` from a heading match plus its line number."""
    return Wave(
        canonical_id=match.group("id"),
        title=match.group("title"),
        intent="",
        line_number=index,
    )


def _build_phase(match: re.Match[str], index: int) -> Phase:
    """Construct a :class:`Phase` from a heading match plus its line number."""
    path = match.group("path")
    return Phase(
        canonical_id=path.split(".")[-1],
        display_path=path,
        title=match.group("title"),
        intent="",
        line_number=index,
    )


def _walk_body(
    body: str,
) -> tuple[list[Wave], list[Phase], list[Step], list[UnknownBlock], bool]:
    """Walk the body and assemble container chains and unknown blocks."""
    waves: list[Wave] = []
    phases: list[Phase] = []
    steps: list[Step] = []
    unknown_blocks: list[UnknownBlock] = []

    current_wave: Wave | None = None
    current_phase: Phase | None = None
    intent_target: Wave | Phase | None = None
    intent_buffer: list[str] = []

    buffered_unknown: list[str] = []
    in_epic_intent: bool = False
    in_link_rules_comment: bool = False
    has_link_rules = False

    def _flush_intent() -> None:
        if intent_target is not None and intent_buffer:
            intent_target.intent = "\n".join(intent_buffer).strip()
        intent_buffer.clear()

    def _flush_unknown(anchor: str) -> None:
        if buffered_unknown:
            content = "\n".join(buffered_unknown).strip()
            if content.strip():
                unknown_blocks.append(UnknownBlock(anchor=anchor, content=content))
            buffered_unknown.clear()

    for index, line in enumerate(body.splitlines(), start=1):
        tokens = _match_line(line)

        # 1. H1 Title line
        if tokens.title:
            _flush_unknown("before_title")
            continue

        # 2. Link rules comment block
        if "<!-- LINK RULES:" in line:
            has_link_rules = True
            in_link_rules_comment = True
        if in_link_rules_comment:
            if "-->" in line:
                in_link_rules_comment = False
            continue

        # 3. Retired comment ledger
        if _RE_RETIRED_LEDGER.search(line):
            continue

        # 4. Epic intent heading
        if tokens.epic_intent:
            _flush_intent()
            intent_target = None
            _flush_unknown("before_epic_intent")
            in_epic_intent = True
            continue

        if in_epic_intent:
            if tokens.opens_a_structural_block():
                in_epic_intent = False
            else:
                continue

        # 5. Steps section heading
        #
        # Consumed, never buffered: the serialiser owns this heading and
        # re-emits it, so letting it fall through to ``buffered_unknown``
        # would duplicate it on every round trip. Dropping it here is safe
        # precisely because the emission is unconditional.
        if tokens.steps_heading:
            _flush_intent()
            intent_target = None
            _flush_unknown("before_steps")
            continue

        # 6. Wave heading
        if tokens.wave:
            _flush_intent()
            current_wave = _build_wave(tokens.wave, index)
            _flush_unknown(f"before_wave_{current_wave.canonical_id}")
            waves.append(current_wave)
            current_phase = None
            intent_target = current_wave
            continue

        # 7. Phase heading
        if tokens.phase:
            _flush_intent()
            current_phase = _build_phase(tokens.phase, index)
            _flush_unknown(f"before_phase_{current_phase.canonical_id}")
            phases.append(current_phase)
            if current_wave is not None:
                current_wave.phases.append(current_phase)
            intent_target = current_phase
            continue

        # 8. Step row
        if tokens.step:
            _flush_intent()
            intent_target = None
            step = _build_step(tokens.step, index, line)
            _flush_unknown(f"before_step_{step.canonical_id}")
            steps.append(step)
            if current_phase is not None:
                current_phase.steps.append(step)
            continue

        # 9. Intent paragraph checking
        if intent_target is not None:
            stripped = line.strip()
            if (
                stripped.startswith("# ")
                or stripped.startswith("## ")
                or stripped.startswith("### ")
            ):
                _flush_intent()
                intent_target = None
            else:
                intent_buffer.append(line)
                continue

        # 10. Fallthrough to unknown buffered lines
        buffered_unknown.append(line)

    _flush_intent()
    _flush_unknown("after_all")

    return waves, phases, steps, unknown_blocks, has_link_rules


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
