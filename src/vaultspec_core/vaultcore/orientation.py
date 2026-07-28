"""Vault orientation rollup and grounding-trace data layer.

This is the pure data core behind ``vaultspec-core status`` (the
vault-orientation ADR's decisions D2, D4, D5, and D6). It computes two
read-only views and prints nothing: the CLI verb in the next phase
renders these structures directly, so every field is pre-shaped (stems,
display paths, counts, percentages) and needs no recomputation at render
time.

- :func:`compute_rollup` returns the vault-wide :class:`Rollup`: active
  (non-archived) features ordered by latest activity, plans in flight
  with open/closed counts and completion percent, recently modified
  documents grouped by type, and totals echoing
  :func:`~vaultspec_core.vaultcore.query.get_stats` (decisions D2/D4).
- :func:`compute_trace` returns the targeted :class:`GroundingTrace`:
  for a plan stem, plan path, or feature tag, each plan's steps mapped to
  their execution-record stems (or ``None`` for open steps without a
  record, or the explicit unlinked bucket for records that reference the
  plan without a resolvable step id), plus grounding documents grouped by
  type from the plan's graph neighbours (decision D5).

Recency follows decision D3b: each document's sort key is its leniently
parsed ``modified:`` stamp, falling back to ``date:``, then to the
filename date prefix; a document with no parseable date sorts last and
never crashes the rollup.

The graph is used internally for traceback (decision D5) but never leaks
into the output: every returned structure is a plain dataclass of stems
and scalars, with no ``networkx`` types, node objects, or edge lists.

This module is the public surface: the data model (dataclasses,
lifecycle status, recency helpers), the rollup computation, and the
grounding-trace computation live in the sibling modules
:mod:`~vaultspec_core.vaultcore.orientation_models`,
:mod:`~vaultspec_core.vaultcore.orientation_rollup`, and
:mod:`~vaultspec_core.vaultcore.orientation_trace` respectively, and are
re-exported here unchanged.
"""

from __future__ import annotations

from .orientation_models import (
    ActiveFeature,
    ExecActivity,
    GroundingTrace,
    PlanInFlight,
    PlanTrace,
    RecentDocument,
    Rollup,
    StepTrace,
    TargetResolutionError,
    feature_lifecycle_status,
)
from .orientation_rollup import compute_rollup
from .orientation_trace import compute_trace

__all__ = [
    "ActiveFeature",
    "ExecActivity",
    "GroundingTrace",
    "PlanInFlight",
    "PlanTrace",
    "RecentDocument",
    "Rollup",
    "StepTrace",
    "TargetResolutionError",
    "compute_rollup",
    "compute_trace",
    "feature_lifecycle_status",
]
