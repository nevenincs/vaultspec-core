"""Display-path computation for Steps, Phases, and Waves.

The convention ADR's *Identifiers and addressing* section defines the
display path as a tier-conditional concatenation of the canonical
identifiers along the current ancestor chain, joined with ``.``. The
display path is **computed at render time**; the canonical identifier
is the leaf segment and never changes when a Step is re-parented or
re-positioned.

This module implements the computation in two flavours:

- :func:`step_display_path` / :func:`phase_display_path` /
  :func:`wave_display_path` accept the relevant canonical-id ancestry
  and return the rendered string. Use these when synthesising a path
  outside the parsed model (e.g., during a CLI move operation).
- :func:`compute_display_paths` walks a parsed :class:`Plan` and
  recomputes every display path from the current grouping, returning
  a dict keyed by canonical Step / Phase / Wave id. Use this to
  detect drift (stored display path differs from computed) or to
  refresh display paths after a re-parenting operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vaultspec_core.plan.frontmatter import Tier

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "DisplayPathTable",
    "compute_display_paths",
    "phase_display_path",
    "step_display_path",
    "wave_display_path",
]


@dataclass
class DisplayPathTable:
    """Display paths keyed by canonical identifier.

    Attributes:
        steps: Map from Step canonical id (``S##``) to its computed
            display path.
        phases: Map from Phase canonical id (``P##``) to its display
            path (with optional Wave ancestor).
        waves: Map from Wave canonical id (``W##``) to its display path
            (always equal to the canonical id at ``L3``/``L4``).
    """

    steps: dict[str, str]
    phases: dict[str, str]
    waves: dict[str, str]


def step_display_path(
    *,
    step_id: str,
    phase_id: str | None = None,
    wave_id: str | None = None,
) -> str:
    """Render the display path for a Step given its ancestor chain.

    Args:
        step_id: Canonical Step identifier (e.g., ``S03``).
        phase_id: Parent Phase identifier (``P##``) when the plan tier
            is at least ``L2``. Pass ``None`` for ``L1`` plans.
        wave_id: Parent Wave identifier (``W##``) when the plan tier is
            at least ``L3``. Pass ``None`` for ``L1`` and ``L2`` plans.

    Returns:
        Concatenated display path:

        - ``S##`` when both ancestors are ``None`` (``L1``).
        - ``P##.S##`` when only ``phase_id`` is supplied (``L2``).
        - ``W##.P##.S##`` when both ancestors are supplied (``L3`` or
          ``L4``; the Epic frame is implicit).

    Raises:
        ValueError: When ``wave_id`` is supplied without ``phase_id``;
            a Wave parent without a Phase parent is not a legal shape.
    """
    if wave_id is not None and phase_id is None:
        msg = "wave_id requires phase_id; cannot have a Wave parent without a Phase"
        raise ValueError(msg)
    segments = [s for s in (wave_id, phase_id, step_id) if s is not None]
    return ".".join(segments)


def phase_display_path(
    *,
    phase_id: str,
    wave_id: str | None = None,
) -> str:
    """Render the display path for a Phase given its (optional) Wave ancestor.

    Args:
        phase_id: Canonical Phase identifier (``P##``).
        wave_id: Parent Wave identifier (``W##``) at ``L3``/``L4``.
            Pass ``None`` for ``L2`` plans.

    Returns:
        ``P##`` at ``L2``; ``W##.P##`` at ``L3`` and ``L4``.
    """
    if wave_id is None:
        return phase_id
    return f"{wave_id}.{phase_id}"


def wave_display_path(*, wave_id: str) -> str:
    """Render the display path for a Wave heading.

    Args:
        wave_id: Canonical Wave identifier (``W##``).

    Returns:
        The Wave canonical id; Wave headings have no ancestor segments
        because the Epic frame is implicit at ``L4``.
    """
    return wave_id


def compute_display_paths(plan: Plan) -> DisplayPathTable:
    """Walk ``plan`` and emit a :class:`DisplayPathTable` for every container.

    The computation reflects the **current** grouping; running this
    against a freshly-parsed plan and comparing to the stored display
    paths surfaces any drift introduced by hand-edits or interrupted
    multi-step CLI operations.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        :class:`DisplayPathTable` keyed by canonical id at every level.
    """
    tier = plan.frontmatter.tier
    steps: dict[str, str] = {}
    phases: dict[str, str] = {}
    waves: dict[str, str] = {}

    if tier in (Tier.L3, Tier.L4):
        for wave in plan.waves:
            waves[wave.canonical_id] = wave_display_path(wave_id=wave.canonical_id)
            for phase in wave.phases:
                phases[phase.canonical_id] = phase_display_path(
                    phase_id=phase.canonical_id,
                    wave_id=wave.canonical_id,
                )
                for step in phase.steps:
                    steps[step.canonical_id] = step_display_path(
                        step_id=step.canonical_id,
                        phase_id=phase.canonical_id,
                        wave_id=wave.canonical_id,
                    )
        return DisplayPathTable(steps=steps, phases=phases, waves=waves)

    if tier is Tier.L2:
        for phase in plan.phases:
            phases[phase.canonical_id] = phase_display_path(
                phase_id=phase.canonical_id,
            )
            for step in phase.steps:
                steps[step.canonical_id] = step_display_path(
                    step_id=step.canonical_id,
                    phase_id=phase.canonical_id,
                )
        return DisplayPathTable(steps=steps, phases=phases, waves=waves)

    # L1: flat Step list.
    for step in plan.steps:
        steps[step.canonical_id] = step_display_path(step_id=step.canonical_id)
    return DisplayPathTable(steps=steps, phases=phases, waves=waves)
