"""Targeted grounding-trace computation for vault orientation (decision D5).

Sibling of :mod:`vaultspec_core.vaultcore.orientation_models` (the
dataclasses this module builds) and
:mod:`vaultspec_core.vaultcore.orientation_rollup` (the vault-wide
counterpart view). :func:`compute_trace` is the only entry point: it
resolves a plan stem, plan path, or feature tag to one
:class:`~vaultspec_core.vaultcore.orientation_models.GroundingTrace`,
mapping each plan's steps to their execution-record stems and grouping
grounding documents from the plan's graph neighbours.

The public surface re-exports every name from
:mod:`vaultspec_core.vaultcore.orientation`; import from there, not this
module, at call sites outside the package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DocType
from .orientation_models import (
    GroundingTrace,
    PlanTrace,
    StepTrace,
    TargetResolutionError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ..graph.api import VaultGraph
    from ..plan.status import ExecRecordIndex

__all__ = ["compute_trace"]

#: Document types that count as grounding context for a plan; everything
#: else (notably ``exec``) is handled by the step-to-record mapping and
#: the unlinked bucket rather than the grounding grouping.
_GROUNDING_TYPES = frozenset(
    {
        DocType.ADR.value,
        DocType.RESEARCH.value,
        DocType.REFERENCE.value,
        DocType.PLAN.value,
        DocType.AUDIT.value,
    }
)


def compute_trace(
    root_dir: Path,
    target: str,
    *,
    graph: VaultGraph | None = None,
    with_paths: bool = False,
) -> GroundingTrace:
    """Compute the grounding trace for a target (decision D5).

    Target resolution precedence is exact plan stem, then plan path,
    then feature tag. An ambiguous or unknown target raises
    :class:`TargetResolutionError` carrying near-matches.

    Args:
        root_dir: Project root directory.
        target: A plan stem, a plan path, or a feature tag (with or
            without the leading ``#``).
        graph: Optional pre-built :class:`~vaultspec_core.graph.VaultGraph`
            to reuse; one is built from *root_dir* when omitted.
        with_paths: When ``True``, populate :attr:`GroundingTrace.paths`
            with the repo-relative path of every referenced document stem
            so file discovery yields openable paths.

    Returns:
        A :class:`GroundingTrace` with one :class:`PlanTrace` per plan
        under the resolved target.

    Raises:
        TargetResolutionError: When the target resolves to no plan or
            feature.
    """
    from ..graph.api import VaultGraph
    from ..plan.status import ExecRecordIndex

    g = graph if graph is not None else VaultGraph(root_dir)
    exec_index = ExecRecordIndex.build(root_dir, graph=g)

    plan_stems = {
        name
        for name, node in g.nodes.items()
        if not node.phantom and node.doc_type is DocType.PLAN
    }

    kind, stems = _resolve_target(target, plan_stems, g)

    plans = [_plan_trace(g, exec_index, stem) for stem in sorted(stems)]
    paths = _trace_paths(g, root_dir, plans) if with_paths else {}
    return GroundingTrace(target=target, kind=kind, plans=plans, paths=paths)


def _trace_paths(
    graph: VaultGraph,
    root_dir: Path,
    plans: list[PlanTrace],
) -> dict[str, str]:
    """Map every stem a trace references to its repo-relative path.

    Sources every plan stem, step record, summary, unlinked record, and
    grounding stem, resolving each through its graph node's backing path.
    Stems with no backing file (phantom or pathless) are omitted rather
    than mapped to a fabricated path. The graph stays internal (decision
    D5/D7); only plain relative-path strings leave this function.
    """
    stems: set[str] = set()
    for plan in plans:
        stems.add(plan.stem)
        stems.update(step.record_stem for step in plan.steps if step.record_stem)
        stems.update(plan.unlinked_records)
        for grounded in plan.grounding.values():
            stems.update(grounded)

    paths: dict[str, str] = {}
    for stem in stems:
        node = graph.nodes.get(stem)
        if node is None or node.path is None:
            continue
        try:
            rel = node.path.resolve().relative_to(root_dir.resolve())
        except ValueError:
            rel = node.path
        paths[stem] = rel.as_posix()
    return paths


def _resolve_target(
    target: str,
    plan_stems: set[str],
    graph: VaultGraph,
) -> tuple[str, set[str]]:
    """Resolve a trace target to a kind plus the set of plan stems.

    Precedence: exact plan stem > plan path > feature tag.
    """
    from pathlib import Path as _Path

    cleaned = target.strip()

    # 1. Exact plan stem.
    if cleaned in plan_stems:
        return "plan", {cleaned}

    # 2. Plan path (absolute or relative; with or without .md).
    path_stem = _Path(cleaned).stem
    if path_stem in plan_stems and (
        "/" in cleaned or "\\" in cleaned or cleaned.endswith(".md")
    ):
        return "plan", {path_stem}

    # 3. Feature tag (with or without leading '#').
    feature = cleaned.lstrip("#")
    feature_plans = {
        name for name in plan_stems if graph.nodes[name].feature == feature
    }
    if feature_plans:
        return "feature", feature_plans

    near = _near_matches(cleaned, plan_stems, graph)
    raise TargetResolutionError(target, near)


def _near_matches(
    target: str,
    plan_stems: set[str],
    graph: VaultGraph,
) -> list[str]:
    """Return up to five plausible target suggestions for an unknown target.

    Suggestions are plan stems or feature tags containing the target as a
    case-insensitive substring, sorted for a stable order.
    """
    needle = target.lstrip("#").lower()
    matches: set[str] = set()
    for stem in plan_stems:
        if needle and needle in stem.lower():
            matches.add(stem)
        feature = graph.nodes[stem].feature
        if feature and needle and needle in feature.lower():
            matches.add(f"#{feature}")
    return sorted(matches)[:5]


def _plan_trace(
    graph: VaultGraph,
    exec_index: ExecRecordIndex,
    stem: str,
) -> PlanTrace:
    """Build the :class:`PlanTrace` for a single plan stem (decision D5)."""
    from ..plan.parser import parse_plan
    from ..plan.status import collect_status

    node = graph.nodes[stem]
    feature = node.feature

    if node.path is None:
        return PlanTrace(stem=stem, feature=feature, error="plan has no backing file")

    try:
        plan = parse_plan(node.path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return PlanTrace(
            stem=stem,
            feature=feature,
            error=f"{type(exc).__name__}: {exc}",
        )

    steps: list[StepTrace] = []
    matched_records: set[str] = set()
    for step in plan.steps:
        record_stem = (
            exec_index.record_for(feature, step.canonical_id) if feature else None
        )
        if record_stem is not None:
            matched_records.add(record_stem)
        evidence = (
            exec_index.evidence_for(feature, step.canonical_id) if feature else None
        )
        steps.append(
            StepTrace(
                canonical_id=step.canonical_id,
                display_path=step.display_path,
                checked=step.checked,
                record_stem=record_stem,
                rows=evidence.rows if evidence else None,
                verify=evidence.verify if evidence else None,
            )
        )

    unlinked = _unlinked_records(graph, exec_index, stem, feature, matched_records)
    grounding = _grounding_documents(graph, stem)

    # Reuse the batched status core so the trace header carries the same
    # clean plan-line facts the rollup shows.
    status = collect_status(plan, exec_index=exec_index)

    return PlanTrace(
        stem=stem,
        feature=feature,
        steps=steps,
        unlinked_records=unlinked,
        grounding=grounding,
        tier=status.tier.value,
        total_steps=status.step_count,
        closed_steps=status.steps_completed,
        open_steps=status.step_count - status.steps_completed,
        completion_percent=status.completion_percent,
        wave_count=status.wave_count,
        waves_completed=status.waves_completed,
        phase_count=status.phase_count,
        phases_completed=status.phases_completed,
        next_open_step=status.next_open_step,
        exec_missing=len(status.exec_missing_ids),
    )


def _unlinked_records(
    graph: VaultGraph,
    exec_index: ExecRecordIndex,
    stem: str,
    feature: str | None,
    matched_records: set[str],
) -> list[str]:
    """Return exec records that reference the plan but map to no step.

    Two sources contribute (decision D5): the feature's records whose
    ``step_id:`` was absent (the index's unlinked bucket), and any exec
    record that links to the plan (graph in-link or ``related:``) yet did
    not map to a step. Records already matched to a step are excluded.
    """
    candidates: set[str] = set()

    if feature:
        for record in exec_index.unlinked_by_feature.get(feature, []):
            candidates.add(record)

    node = graph.nodes[stem]
    for src in node.in_links:
        src_node = graph.nodes.get(src)
        if (
            src_node is not None
            and src_node.doc_type is DocType.EXEC
            and src not in matched_records
        ):
            candidates.add(src)

    return sorted(candidates - matched_records)


def _grounding_documents(graph: VaultGraph, stem: str) -> dict[str, list[str]]:
    """Group the plan's grounding neighbours by document type (decision D5).

    Outgoing ``related:`` neighbours (adr, research, reference, prior
    plan, audit) plus incoming non-exec references are collected as
    stems and grouped by type. Exec in-links are deliberately excluded
    here; they are the step-to-record concern.
    """
    node = graph.nodes[stem]
    grouped: dict[str, set[str]] = {}

    def _add(neighbour_name: str) -> None:
        neighbour = graph.nodes.get(neighbour_name)
        if neighbour is None or neighbour.phantom or neighbour.doc_type is None:
            return
        if neighbour_name == stem:
            return
        doc_type = neighbour.doc_type.value
        if doc_type not in _GROUNDING_TYPES:
            return
        grouped.setdefault(doc_type, set()).add(neighbour_name)

    for out in node.out_links:
        _add(out)
    for inc in node.in_links:
        _add(inc)

    return {doc_type: sorted(stems) for doc_type, stems in sorted(grouped.items())}
