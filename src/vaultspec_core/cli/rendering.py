"""CLI-layer rendering helpers for dry-run previews and sync summaries.

All Rich/console output for structured previews lives here, not in core.
Key exports: :func:`render_dry_run_tree` and the canonical outcome
vocabulary (:class:`Outcome`, :func:`render_outcomes`,
:func:`outcomes_as_json`). Depends on :mod:`vaultspec_core.core.dry_run`
for :class:`~vaultspec_core.core.dry_run.DryRunItem` and status styles;
consumed by :mod:`.root` and indirectly by :mod:`.vault_cmd`.

This module is the public surface for CLI rendering: the implementations
live in sibling modules, split along seam (:mod:`.rendering_outcomes` for
the ``Outcome`` vocabulary and the ``--json`` envelope,
:mod:`.rendering_shapes` for the Record/Listing/Tree output contract,
:mod:`.rendering_summaries` for the install/uninstall/sharing-policy
banners, :mod:`.rendering_hints` for the next-step-hint footer, and
:mod:`.rendering_plan` for the plan-overview row shape). Importing this
module re-exports the full prior public surface so no import site
outside the package needs to change.
"""

from __future__ import annotations

from vaultspec_core.cli.rendering_hints import (
    SafeDict,
    emit_next_step_hint,
    hints_suppressed,
    render_next_actions,
)
from vaultspec_core.cli.rendering_outcomes import (
    OUTCOME_STYLE,
    Outcome,
    OutcomeItem,
    aggregate_outcome,
    count_outcomes,
    emit_outcomes,
    json_envelope,
    outcomes_as_json,
    render_outcomes,
    sync_outcomes,
)
from vaultspec_core.cli.rendering_plan import (
    active_feature_tail,
    align_plan_rows,
    plan_line_cells,
)
from vaultspec_core.cli.rendering_shapes import (
    TRUNCATE_MARKER,
    Cell,
    Column,
    Field,
    TreeLine,
    emit_listing,
    emit_record,
    listing_as_json,
    record_as_json,
    render_dry_run_tree,
    render_listing,
    render_record,
    render_tree,
    summary_line,
    truncate,
)
from vaultspec_core.cli.rendering_summaries import (
    render_install_summary,
    render_sharing_policy,
    render_uninstall_summary,
)

__all__ = [
    "OUTCOME_STYLE",
    "TRUNCATE_MARKER",
    "Cell",
    "Column",
    "Field",
    "Outcome",
    "OutcomeItem",
    "SafeDict",
    "TreeLine",
    "active_feature_tail",
    "aggregate_outcome",
    "align_plan_rows",
    "count_outcomes",
    "emit_listing",
    "emit_next_step_hint",
    "emit_outcomes",
    "emit_record",
    "hints_suppressed",
    "json_envelope",
    "listing_as_json",
    "outcomes_as_json",
    "plan_line_cells",
    "record_as_json",
    "render_dry_run_tree",
    "render_install_summary",
    "render_listing",
    "render_next_actions",
    "render_outcomes",
    "render_record",
    "render_sharing_policy",
    "render_tree",
    "render_uninstall_summary",
    "summary_line",
    "sync_outcomes",
    "truncate",
]
