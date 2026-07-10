"""Orientation-domain MCP tools: read-only ``status`` and repair-capable ``check``.

Both tools are thin wrappers over their owning cores - no orientation or
validation logic is authored in this layer. ``status`` renders
:func:`~vaultspec_core.vaultcore.orientation.compute_rollup` for the
unparameterized project view and
:func:`~vaultspec_core.vaultcore.orientation.compute_trace` for a targeted
feature-or-plan trace, and returns no blob hashes (orientation is
hash-free; the read-then-edit chain sources hashes from ``find``). ``check``
runs :func:`~vaultspec_core.vaultcore.checks.run_all_checks` with an optional
``fix`` and returns the structured findings. Both declare their structured
output through typed Pydantic return models.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ... import __version__
from ...core.types import get_context as _get_ctx
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...vaultcore.checks import CheckResult
    from ...vaultcore.orientation import GroundingTrace, Rollup

logger = logging.getLogger(__name__)

__all__ = ["register_orientation_tools"]


# ---------------------------------------------------------------------------
# status output models
# ---------------------------------------------------------------------------


class FeatureStatus(BaseModel):
    """One active feature in the project-wide orientation view.

    Attributes:
        name: The feature tag without ``#``.
        doc_count: Number of non-archived documents carrying the tag.
        latest_activity: The most recent ``yyyy-mm-dd`` across the feature's
            documents, or ``None``.
        has_plan: Whether the feature has at least one plan.
        status: The lifecycle status word from the orientation core.
        plan_tier: The feature's plan tier, or ``None``.
        plan_completion_percent: The feature's plan completion percent.
    """

    name: str
    doc_count: int
    latest_activity: str | None
    has_plan: bool
    status: str
    plan_tier: str | None = None
    plan_completion_percent: float = 0.0


class PlanProgressLine(BaseModel):
    """A plan in flight, pre-shaped for the orientation view.

    Attributes:
        stem: The plan document's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
        tier: The plan's complexity tier value.
        open_steps: Number of unchecked steps.
        closed_steps: Number of checked steps.
        total_steps: Total step count.
        completion_percent: Completion percent.
        next_open_step: Display path of the first open step, or ``None``.
    """

    stem: str
    feature: str | None
    tier: str
    open_steps: int
    closed_steps: int
    total_steps: int
    completion_percent: float
    next_open_step: str | None


class StepTraceLine(BaseModel):
    """One plan step mapped to its execution record in a trace.

    Attributes:
        canonical_id: The step's canonical leaf identifier (``S##``).
        display_path: The step's tier-conditional display path.
        checked: Whether the step's checkbox is ``[x]``.
        record_stem: The execution-record stem mapped to this step, or
            ``None`` for an open step with no record.
    """

    canonical_id: str
    display_path: str
    checked: bool
    record_stem: str | None


class PlanTraceLine(BaseModel):
    """The grounding trace for a single plan.

    Attributes:
        stem: The plan document's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
        tier: The plan's tier value, or ``None`` when unparsed.
        total_steps: Total step count.
        closed_steps: Checked-step count.
        open_steps: Unchecked-step count.
        completion_percent: Completion percent.
        next_open_step: Display path of the first open step, or ``None``.
        steps: Per-step record mapping in document order.
        grounding: Grounding documents grouped by document type (stems only).
        summaries: Phase-summary document stems referencing this plan.
        unlinked_records: Execution-record stems referencing the plan
            without a resolvable step id.
        error: A parse-error note when the plan could not be parsed.
    """

    stem: str
    feature: str | None
    tier: str | None
    total_steps: int
    closed_steps: int
    open_steps: int
    completion_percent: float
    next_open_step: str | None
    steps: list[StepTraceLine] = Field(default_factory=list)
    grounding: dict[str, list[str]] = Field(default_factory=dict)
    summaries: list[str] = Field(default_factory=list)
    unlinked_records: list[str] = Field(default_factory=list)
    error: str | None = None


class StatusResult(BaseModel):
    """The whole-call result of a ``status`` invocation.

    Carries no blob hashes: orientation is hash-free, and the read-then-edit
    chain sources hashes from ``find`` instead.

    Attributes:
        tool_schema_version: The tool-schema package version, echoed so it
            survives the stateless protocol where ``initialize`` disappears.
        kind: ``"rollup"`` for the project-wide view or ``"trace"`` for a
            targeted feature-or-plan trace.
        features: Active features (rollup mode only).
        plans_in_flight: Plans with at least one open step (rollup mode only).
        totals: The vault statistics dict (rollup mode only).
        target: The trace target as submitted (trace mode only).
        trace_kind: How the target resolved - ``"plan"`` or ``"feature"``
            (trace mode only).
        plans: One trace per plan under the target (trace mode only).
    """

    tool_schema_version: str
    kind: str
    features: list[FeatureStatus] = Field(default_factory=list)
    plans_in_flight: list[PlanProgressLine] = Field(default_factory=list)
    totals: dict[str, Any] = Field(default_factory=dict)
    target: str | None = None
    trace_kind: str | None = None
    plans: list[PlanTraceLine] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# check output models
# ---------------------------------------------------------------------------


class CheckFinding(BaseModel):
    """One finding from a vault health check.

    Attributes:
        check: The originating checker name (e.g. ``"frontmatter"``).
        path: Relative path to the affected document, or ``None`` for a
            vault-wide finding.
        message: Human-readable description of the issue.
        severity: One of ``error`` / ``warning`` / ``info``.
        fixable: Whether ``fix`` can resolve this finding.
    """

    check: str
    path: str | None
    message: str
    severity: str
    fixable: bool


class CheckReportLine(BaseModel):
    """The per-checker summary line.

    Attributes:
        check: The checker name.
        error_count: ERROR-severity finding count.
        warning_count: WARNING-severity finding count.
        info_count: INFO-severity finding count.
        fixed_count: Issues auto-corrected under ``fix``.
        clean: Whether the checker produced no findings.
    """

    check: str
    error_count: int
    warning_count: int
    info_count: int
    fixed_count: int
    clean: bool


class CheckResultModel(BaseModel):
    """The whole-call result of a ``check`` invocation.

    Attributes:
        status: ``"ok"`` when no error-severity findings remain, else
            ``"failed"``.
        fixed: Whether ``fix`` was applied.
        total_errors: Aggregate error-severity finding count.
        total_warnings: Aggregate warning-severity finding count.
        total_fixed: Aggregate auto-corrected count.
        checks: The per-checker summary lines.
        findings: The flattened error- and warning-severity findings.
    """

    status: str
    fixed: bool
    total_errors: int
    total_warnings: int
    total_fixed: int
    checks: list[CheckReportLine] = Field(default_factory=list)
    findings: list[CheckFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Adapters (core dataclasses -> output models)
# ---------------------------------------------------------------------------


def _rollup_to_result(rollup: Rollup) -> StatusResult:
    """Adapt a :class:`Rollup` into the ``status`` rollup result."""
    return StatusResult(
        tool_schema_version=__version__,
        kind="rollup",
        features=[
            FeatureStatus(
                name=f.name,
                doc_count=f.doc_count,
                latest_activity=f.latest_activity,
                has_plan=f.has_plan,
                status=_lifecycle_status(f),
                plan_tier=f.plan_tier,
                plan_completion_percent=f.plan_completion_percent,
            )
            for f in rollup.active_features
        ],
        plans_in_flight=[
            PlanProgressLine(
                stem=p.stem,
                feature=p.feature,
                tier=p.tier,
                open_steps=p.open_steps,
                closed_steps=p.closed_steps,
                total_steps=p.total_steps,
                completion_percent=p.completion_percent,
                next_open_step=p.next_open_step,
            )
            for p in rollup.plans_in_flight
        ],
        totals=dict(rollup.totals),
    )


def _lifecycle_status(feature: Any) -> str:
    """Derive a rollup feature's lifecycle word via the orientation core.

    The rollup's :class:`ActiveFeature` does not carry the feature's document
    types, so the type-driven pre-plan phases (``Specified`` / ``Researching``)
    are approximated from ``has_plan`` alone here; the fully type-aware
    derivation is exercised by ``find``. Plan-progress phases resolve exactly.
    """
    from ...vaultcore.orientation import feature_lifecycle_status

    return feature_lifecycle_status(feature, set())


def _trace_to_result(trace: GroundingTrace) -> StatusResult:
    """Adapt a :class:`GroundingTrace` into the ``status`` trace result."""
    return StatusResult(
        tool_schema_version=__version__,
        kind="trace",
        target=trace.target,
        trace_kind=trace.kind,
        plans=[
            PlanTraceLine(
                stem=pt.stem,
                feature=pt.feature,
                tier=pt.tier,
                total_steps=pt.total_steps,
                closed_steps=pt.closed_steps,
                open_steps=pt.open_steps,
                completion_percent=pt.completion_percent,
                next_open_step=pt.next_open_step,
                steps=[
                    StepTraceLine(
                        canonical_id=st.canonical_id,
                        display_path=st.display_path,
                        checked=st.checked,
                        record_stem=st.record_stem,
                    )
                    for st in pt.steps
                ],
                grounding=pt.grounding,
                summaries=pt.summaries,
                unlinked_records=pt.unlinked_records,
                error=pt.error,
            )
            for pt in trace.plans
        ],
    )


def _checks_to_result(results: list[CheckResult], *, fix: bool) -> CheckResultModel:
    """Fold the per-checker results into the ``check`` output model."""
    checks: list[CheckReportLine] = []
    findings: list[CheckFinding] = []
    total_errors = 0
    total_warnings = 0
    total_fixed = 0

    for result in results:
        total_errors += result.error_count
        total_warnings += result.warning_count
        total_fixed += result.fixed_count
        checks.append(
            CheckReportLine(
                check=result.check_name,
                error_count=result.error_count,
                warning_count=result.warning_count,
                info_count=result.info_count,
                fixed_count=result.fixed_count,
                clean=result.is_clean,
            )
        )
        for diag in result.diagnostics:
            if diag.severity.value == "info":
                continue
            findings.append(
                CheckFinding(
                    check=result.check_name,
                    path=str(diag.path) if diag.path is not None else None,
                    message=diag.message,
                    severity=diag.severity.value,
                    fixable=diag.fixable,
                )
            )

    return CheckResultModel(
        status="ok" if total_errors == 0 else "failed",
        fixed=fix,
        total_errors=total_errors,
        total_warnings=total_warnings,
        total_fixed=total_fixed,
        checks=checks,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_orientation_tools(mcp: FastMCP) -> None:
    """Register the ``status`` and ``check`` orientation tools on *mcp*.

    ``status`` is read-only and idempotent. ``check`` is annotated
    non-read-only, non-destructive, and idempotent per ADR Q6: it can repair
    with ``fix`` yet re-running it converges, and a repair never destroys
    authored prose. Both declare structured output through their typed
    return models.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def status(ctx: Context, target: str | None = None) -> StatusResult:
        """Orient in a vaultspec project, project-wide or targeted.

        With no ``target``, returns the project rollup: active features with
        their lifecycle status, plans in flight with tier and completion and
        the next open step, and the vault totals, plus the tool-schema
        version. With a ``target`` (a feature tag or a plan stem/path),
        returns the grounding trace for the matching plan(s): each step
        mapped to its execution record, the grounding documents, and the
        completion facts. Returns no blob hashes.

        Args:
            ctx: The MCP request context.
            target: A feature tag or plan stem/path for the targeted trace,
                or ``None`` for the project rollup.

        Returns:
            The :class:`StatusResult` for the requested view.

        Raises:
            ValueError: When a ``target`` resolves to no plan or feature.
        """
        from ...vaultcore.orientation import (
            TargetResolutionError,
            compute_rollup,
            compute_trace,
        )

        root_dir = _get_ctx().target_dir
        if target is None:
            await ctx.info("status: project rollup")
            return _rollup_to_result(compute_rollup(root_dir))

        await ctx.info(f"status: trace target={target!r}")
        try:
            trace = compute_trace(root_dir, target)
        except TargetResolutionError as exc:
            raise ValueError(str(exc)) from exc
        return _trace_to_result(trace)

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def check(
        ctx: Context,
        feature: str | None = None,
        fix: bool = False,
    ) -> CheckResultModel:
        """Run the vault health-check suite, optionally repairing.

        Runs every checker over the vault (optionally restricted to one
        feature) and returns the structured findings. With ``fix``, the
        supporting checkers auto-correct what they safely can and report the
        corrected count; a repair never overwrites authored prose, so
        re-running converges (idempotent).

        Args:
            ctx: The MCP request context.
            feature: Restrict per-document checks to this feature tag
                (without ``#``), or ``None`` for the whole vault.
            fix: When ``True``, apply the safe auto-corrections.

        Returns:
            The :class:`CheckResultModel` with per-checker summaries and the
            flattened error- and warning-severity findings.
        """
        from ...vaultcore.checks import run_all_checks

        await ctx.info(f"check: feature={feature!r} fix={fix}")
        root_dir = _get_ctx().target_dir
        results = run_all_checks(root_dir, feature=feature, fix=fix)
        report = _checks_to_result(results, fix=fix)
        await ctx.debug(
            f"check: {report.total_errors} error(s), "
            f"{report.total_warnings} warning(s), {report.total_fixed} fixed"
        )
        return report
