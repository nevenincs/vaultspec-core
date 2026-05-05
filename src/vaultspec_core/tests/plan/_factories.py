"""Factories for synthesising plan documents in clean and degraded states.

Every factory accepts a :class:`random.Random` for deterministic
randomisation under a fixed seed. The ``make_clean_plan`` entry point
emits a fully-compliant plan at a chosen tier; the ``corrupt_*``
operators apply targeted degradations (padding, checkbox, separator,
period, vocabulary) so tests can exercise the parser's tolerance and
the validator's detection rules.

Plans rendered by these factories are byte-for-byte reproducible
under a fixed seed plus fixed parameters; the randomness only
affects which titles, file scopes, and corruption sites are chosen.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import random

_VERBS: Final[tuple[str, ...]] = (
    "rewrite",
    "add",
    "remove",
    "replace",
    "reconcile",
    "audit",
    "update",
    "extract",
)

_SCOPES: Final[tuple[str, ...]] = (
    "src/module/parser.py",
    "src/module/serialiser.py",
    "src/module/identifiers.py",
    "tests/test_parser.py",
    "docs/README.md",
    "config/settings.yaml",
)

_TIER_HIERARCHY: Final[tuple[str, ...]] = ("L1", "L2", "L3", "L4")


# ---- Spec dataclasses (mirror the parser model) ------------------------------


@dataclass
class StepSpec:
    """Specification for one Step row in the rendered plan."""

    canonical_id: str
    display_path: str
    action: str
    scope: str
    checked: bool = False


@dataclass
class PhaseSpec:
    """Specification for one Phase block: heading, intent, contiguous Steps."""

    canonical_id: str
    display_path: str
    title: str
    intent: str
    steps: list[StepSpec] = field(default_factory=list)


@dataclass
class WaveSpec:
    """Specification for one Wave block (``L3``/``L4`` only)."""

    canonical_id: str
    title: str
    intent: str
    phases: list[PhaseSpec] = field(default_factory=list)


@dataclass
class PlanSpec:
    """Specification for a full plan document.

    Tier-conditional content:

    - ``L1`` populates ``steps``; ``phases``, ``waves``, ``epic_intent``
      remain empty / ``None``.
    - ``L2`` populates ``phases`` (each holding Steps); top-level
      ``steps`` mirrors the flattened descendants for convenience but
      the rendered document only emits Phase blocks.
    - ``L3`` populates ``waves`` (each holding Phases of Steps); top-
      level ``phases`` and ``steps`` mirror the flattened descendants.
    - ``L4`` adds a non-``None`` ``epic_intent``.
    """

    tier: str
    feature: str
    title: str
    related: list[str]
    epic_intent: str | None = None
    waves: list[WaveSpec] = field(default_factory=list)
    phases: list[PhaseSpec] = field(default_factory=list)
    steps: list[StepSpec] = field(default_factory=list)
    date: str = "2026-05-05"

    def render(self) -> str:
        """Emit the plan as canonical Markdown text matching the convention."""
        return _render_plan(self)


# ---- Clean factories ---------------------------------------------------------


def make_clean_plan(
    tier: str,
    *,
    rng: random.Random,
    waves: int = 0,
    phases: int = 0,
    steps: int = 0,
    feature: str = "test-feature",
) -> PlanSpec:
    """Build a fully-compliant :class:`PlanSpec` at the requested tier.

    Args:
        tier: One of ``L1``, ``L2``, ``L3``, ``L4``.
        rng: Deterministic random source.
        waves: Number of Waves at ``L3``/``L4``. Ignored at ``L1``/``L2``.
        phases: Number of Phases at ``L2``, or per-Wave at ``L3``/``L4``.
            Ignored at ``L1``.
        steps: Number of Steps at ``L1``, or per-Phase at higher tiers.
        feature: Feature tag used in the document title.

    Returns:
        :class:`PlanSpec` ready for rendering.

    Raises:
        ValueError: When ``tier`` is not one of the four canonical values.
    """
    if tier not in _TIER_HIERARCHY:
        raise ValueError(f"unknown tier {tier!r}; expected one of {_TIER_HIERARCHY}")

    counter = _IdCounter()
    related = [f"[[2026-05-05-{feature}-adr]]"]
    title = f"{feature} {tier} plan"

    if tier == "L1":
        l1_steps = [
            _make_step_spec(counter, ancestors=(), rng=rng)
            for _ in range(max(steps, 1))
        ]
        return PlanSpec(
            tier=tier,
            feature=feature,
            title=title,
            related=related,
            steps=l1_steps,
        )

    if tier == "L2":
        phase_count = max(phases, 1)
        l2_phases = [
            _make_phase_spec(
                counter,
                ancestors=(),
                steps_count=max(steps, 1),
                rng=rng,
            )
            for _ in range(phase_count)
        ]
        return PlanSpec(
            tier=tier,
            feature=feature,
            title=title,
            related=related,
            phases=l2_phases,
            steps=[s for p in l2_phases for s in p.steps],
        )

    wave_count = max(waves, 1)
    phase_count = max(phases, 1)
    step_count = max(steps, 1)
    l3_waves = [
        _make_wave_spec(
            counter,
            phases_count=phase_count,
            steps_count=step_count,
            rng=rng,
        )
        for _ in range(wave_count)
    ]
    flattened_phases = [p for w in l3_waves for p in w.phases]
    flattened_steps = [s for p in flattened_phases for s in p.steps]

    epic_intent = (
        f"Strategic goal for {feature}. PM association: project board "
        f"{feature.upper()}-2026."
        if tier == "L4"
        else None
    )

    return PlanSpec(
        tier=tier,
        feature=feature,
        title=title,
        related=related,
        epic_intent=epic_intent,
        waves=l3_waves,
        phases=flattened_phases,
        steps=flattened_steps,
    )


# ---- Corruption operators ---------------------------------------------------


def corrupt_padding(text: str, *, rng: random.Random) -> str:
    """Strip the leading zero from one randomly-chosen Step identifier.

    Returns text where one ``S0X`` becomes ``SX`` (e.g., ``S03`` -> ``S3``).
    The corruption violates the convention's two-digit minimum padding
    rule; the parser's regex (``S\\d{2,}``) refuses to match the
    corrupted row, so the row is silently skipped.
    """
    matches = list(_iter_step_id_positions(text))
    if not matches:
        return text
    target = rng.choice(matches)
    return _replace_at(text, target.start, target.end, target.value.replace("0", "", 1))


def corrupt_checkbox(text: str, *, rng: random.Random) -> str:
    """Mangle one randomly-chosen checkbox to a non-canonical state.

    Replaces ``- [ ]`` with ``- []`` (no internal space) or ``- [x]``
    with ``- [X]`` (uppercase). Either form fails the row regex; the
    row is silently skipped by the parser.
    """
    rows = [i for i, line in enumerate(text.splitlines()) if line.startswith("- [")]
    if not rows:
        return text
    lines = text.splitlines()
    target = rng.choice(rows)
    line = lines[target]
    lines[target] = line.replace("- [ ]", "- []", 1).replace("- [x]", "- [X]", 1)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def corrupt_separator(text: str, *, rng: random.Random) -> str:
    """Replace one ASCII spaced hyphen with an em-dash on a random row.

    The em-dash (U+2014) is forbidden everywhere; the corrupted row
    fails the regex and is silently skipped.
    """
    rows = [i for i, line in enumerate(text.splitlines()) if line.startswith("- [")]
    if not rows:
        return text
    lines = text.splitlines()
    target = rng.choice(rows)
    lines[target] = lines[target].replace(" - ", " — ", 1)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def corrupt_drop_period(text: str, *, rng: random.Random) -> str:
    """Remove the trailing period from one randomly-chosen Step row.

    The parser's ``_split_action_and_scope`` strips the trailing period
    before splitting on ``;``; the row is still parsed, but the test
    asserts the resilient behaviour.
    """
    lines = text.splitlines()
    rows = [i for i, line in enumerate(lines) if line.startswith("- [")]
    if not rows:
        return text
    target = rng.choice(rows)
    lines[target] = lines[target].rstrip(".")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def corrupt_lowercase_id(text: str, *, rng: random.Random) -> str:
    """Lowercase one Step's canonical identifier (``S03`` -> ``s03``).

    The parser's regex requires uppercase ``S\\d{2,}``; lowercase rows
    fail to match and are silently skipped.
    """
    matches = list(_iter_step_id_positions(text))
    if not matches:
        return text
    target = rng.choice(matches)
    return _replace_at(text, target.start, target.end, target.value.lower())


def inject_gap(spec: PlanSpec, *, rng: random.Random) -> PlanSpec:
    """Drop one Step from ``spec`` to create a permanent gap in the sequence.

    Returns a new :class:`PlanSpec` with one Step removed; the canonical
    identifiers of remaining Steps are unchanged (gap stays visible).
    """
    if not spec.steps:
        return spec
    victim = rng.choice(spec.steps)
    new_phases = [
        PhaseSpec(
            canonical_id=p.canonical_id,
            display_path=p.display_path,
            title=p.title,
            intent=p.intent,
            steps=[s for s in p.steps if s.canonical_id != victim.canonical_id],
        )
        for p in spec.phases
    ]
    new_waves = [
        WaveSpec(
            canonical_id=w.canonical_id,
            title=w.title,
            intent=w.intent,
            phases=[
                PhaseSpec(
                    canonical_id=p.canonical_id,
                    display_path=p.display_path,
                    title=p.title,
                    intent=p.intent,
                    steps=[s for s in p.steps if s.canonical_id != victim.canonical_id],
                )
                for p in w.phases
            ],
        )
        for w in spec.waves
    ]
    new_top_steps = [s for s in spec.steps if s.canonical_id != victim.canonical_id]
    return PlanSpec(
        tier=spec.tier,
        feature=spec.feature,
        title=spec.title,
        related=spec.related,
        epic_intent=spec.epic_intent,
        waves=new_waves,
        phases=new_phases,
        steps=new_top_steps,
        date=spec.date,
    )


# ---- Internals --------------------------------------------------------------


@dataclass
class _IdMatch:
    """Position of a Step identifier within a rendered plan text."""

    start: int
    end: int
    value: str


@dataclass
class _IdCounter:
    """Per-document append-only counter for ``S##``, ``P##``, ``W##``."""

    next_step: int = 1
    next_phase: int = 1
    next_wave: int = 1

    def step(self) -> str:
        identifier = f"S{self.next_step:02d}"
        self.next_step += 1
        return identifier

    def phase(self) -> str:
        identifier = f"P{self.next_phase:02d}"
        self.next_phase += 1
        return identifier

    def wave(self) -> str:
        identifier = f"W{self.next_wave:02d}"
        self.next_wave += 1
        return identifier


def _make_step_spec(
    counter: _IdCounter,
    *,
    ancestors: tuple[str, ...],
    rng: random.Random,
) -> StepSpec:
    canonical = counter.step()
    display = ".".join((*ancestors, canonical))
    verb = rng.choice(_VERBS)
    target = rng.choice(_SCOPES)
    suffix = "".join(rng.choice(string.ascii_lowercase) for _ in range(4))
    action = f"{verb} the {suffix} component"
    return StepSpec(
        canonical_id=canonical,
        display_path=display,
        action=action,
        scope=target,
    )


def _make_phase_spec(
    counter: _IdCounter,
    *,
    ancestors: tuple[str, ...],
    steps_count: int,
    rng: random.Random,
) -> PhaseSpec:
    phase_id = counter.phase()
    phase_path = ".".join((*ancestors, phase_id))
    title = f"phase {phase_id.lower()} title"
    intent = f"Phase {phase_id} delivers a coherent slice of the work."
    step_specs = [
        _make_step_spec(counter, ancestors=(*ancestors, phase_id), rng=rng)
        for _ in range(steps_count)
    ]
    return PhaseSpec(
        canonical_id=phase_id,
        display_path=phase_path,
        title=title,
        intent=intent,
        steps=step_specs,
    )


def _make_wave_spec(
    counter: _IdCounter,
    *,
    phases_count: int,
    steps_count: int,
    rng: random.Random,
) -> WaveSpec:
    wave_id = counter.wave()
    title = f"wave {wave_id.lower()} title"
    intent = (
        f"Wave {wave_id} delivers a shippable batch with hard "
        f"interdependency on prior Waves."
    )
    phase_specs = [
        _make_phase_spec(
            counter,
            ancestors=(wave_id,),
            steps_count=steps_count,
            rng=rng,
        )
        for _ in range(phases_count)
    ]
    return WaveSpec(
        canonical_id=wave_id,
        title=title,
        intent=intent,
        phases=phase_specs,
    )


def _render_plan(spec: PlanSpec) -> str:
    """Render a :class:`PlanSpec` as Markdown matching the convention."""
    parts: list[str] = []
    parts.append(_render_frontmatter(spec))
    parts.append("")
    parts.append(f"# `{spec.feature}` plan")
    parts.append("")
    parts.append(spec.title)
    parts.append("")

    if spec.tier == "L4" and spec.epic_intent is not None:
        parts.append("## Epic intent")
        parts.append("")
        parts.append(spec.epic_intent)
        parts.append("")

    if spec.tier == "L1":
        for step in spec.steps:
            parts.append(_render_step_row(step))
    elif spec.tier == "L2":
        for phase in spec.phases:
            parts.extend(_render_phase_block(phase))
    else:  # L3 or L4
        for wave in spec.waves:
            parts.extend(_render_wave_block(wave))

    return "\n".join(parts) + "\n"


def _render_frontmatter(spec: PlanSpec) -> str:
    related_lines = "\n".join(f"  - '{wl}'" for wl in spec.related)
    return (
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        f"  - '#{spec.feature}'\n"
        f"date: '{spec.date}'\n"
        f"tier: {spec.tier}\n"
        "related:\n"
        f"{related_lines}\n"
        "---"
    )


def _render_step_row(step: StepSpec) -> str:
    state = "x" if step.checked else " "
    return f"- [{state}] `{step.display_path}` - {step.action}; `{step.scope}`."


def _render_phase_block(phase: PhaseSpec) -> list[str]:
    lines = [
        f"### Phase `{phase.display_path}` - {phase.title}",
        "",
        phase.intent,
        "",
    ]
    for step in phase.steps:
        lines.append(_render_step_row(step))
    lines.append("")
    return lines


def _render_wave_block(wave: WaveSpec) -> list[str]:
    lines = [
        f"## Wave `{wave.canonical_id}` - {wave.title}",
        "",
        wave.intent,
        "",
    ]
    for phase in wave.phases:
        lines.extend(_render_phase_block(phase))
    return lines


def _iter_step_id_positions(text: str):
    """Yield :class:`_IdMatch` for each Step identifier occurrence."""
    import re

    pattern = re.compile(r"`S\d{2,}`")
    for match in pattern.finditer(text):
        # Skip the leading and trailing backtick from the substring we mutate.
        value = match.group(0).strip("`")
        yield _IdMatch(start=match.start() + 1, end=match.end() - 1, value=value)


def _replace_at(text: str, start: int, end: int, replacement: str) -> str:
    """Return ``text`` with ``text[start:end]`` swapped for ``replacement``."""
    return text[:start] + replacement + text[end:]
