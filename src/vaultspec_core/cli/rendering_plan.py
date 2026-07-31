"""Clean plan-line rendering: the plan-overview row shape.

Split out of :mod:`.rendering`. Re-exported from there so no import site
outside the package needs to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def plan_line_cells(
    *,
    name: str,
    tier: str | None,
    waves_completed: int,
    wave_count: int,
    phases_completed: int,
    phase_count: int,
    steps_completed: int,
    step_count: int,
    completion_percent: float,
    next_open_step: str | None,
    exec_missing: int = 0,
) -> list[str]:
    """Return the column cells of one clean plan-overview line.

    The line is deliberately glyph-free and label-light so it reads the
    same everywhere it appears - the rollup's in-flight and recently-
    completed rows and the targeted-trace header. Containers the tier does
    not use render as ``-`` (no Waves at L1/L2; no Phases at L1). The
    cursor cell names the next open step, or ``complete`` when none remain.
    A non-zero *exec_missing* count renders a trailing ``!n`` flag so a
    checked-but-ungrounded plan is visible at a glance.

    Returns a fixed eight-cell row so a column of rows aligns under
    :func:`align_plan_rows`.
    """
    waves = f"W{waves_completed}/{wave_count}" if wave_count else "-"
    phases = f"P{phases_completed}/{phase_count}" if phase_count else "-"
    cursor = f"next {next_open_step}" if next_open_step else "complete"
    flag = f"!{exec_missing}" if exec_missing else ""
    return [
        name,
        tier or "-",
        waves,
        phases,
        f"{steps_completed}/{step_count} steps",
        f"{completion_percent:g}%",
        cursor,
        flag,
    ]


def align_plan_rows(rows: Sequence[Sequence[str]], *, gap: str = "   ") -> list[str]:
    """Left-pad cells column-wise so a set of plan rows aligns cleanly.

    Each row is padded to the per-column maximum width and joined with
    *gap*; trailing whitespace (from empty cells such as an absent
    ``!n`` flag) is stripped so lines never carry dangling spaces.
    """
    if not rows:
        return []
    width = max(len(row) for row in rows)
    col_widths = [
        max(len(row[i]) if i < len(row) else 0 for row in rows) for i in range(width)
    ]
    lines: list[str] = []
    for row in rows:
        padded = [
            (row[i] if i < len(row) else "").ljust(col_widths[i]) for i in range(width)
        ]
        lines.append(gap.join(padded).rstrip())
    return lines


def active_feature_tail(
    *,
    tier: str | None,
    steps_completed: int,
    step_count: int,
    completion_percent: float,
    plan_count: int = 1,
    plans_unreadable: int = 0,
) -> str:
    """Return the condensed plan tail for an active-features row.

    Shorter than the full plan line: just ``<tier> <k>/<N> <p>%``. The
    counts are the feature's combined totals across every plan carrying
    its tag, so a feature planned across several documents appends
    ``across <n> plans`` to say which documents the figure sums. Plans
    that failed to parse contribute no steps and are called out instead
    of quietly reading as zero progress.

    Args:
        tier: Highest tier across the feature's readable plans.
        steps_completed: Checked steps summed over those plans.
        step_count: Total steps summed over those plans.
        completion_percent: Combined completion percent.
        plan_count: Plan documents carrying the feature tag.
        plans_unreadable: How many of those plans failed to parse.

    Returns:
        The tail string, or an empty string when the feature has neither
        steps nor an unreadable plan to report.
    """
    parts: list[str] = []
    if step_count:
        parts.append(
            f"{tier or '-'} {steps_completed}/{step_count} {completion_percent:g}%"
        )
        if plan_count > 1:
            parts.append(f"across {plan_count} plans")
    if plans_unreadable:
        noun = "plan" if plans_unreadable == 1 else "plans"
        parts.append(f"{plans_unreadable} unreadable {noun}")
    return "  ".join(parts)
