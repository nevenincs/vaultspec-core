"""Pair every plan Step with its evidence in the plan's execution ledger.

Execution has one artifact: the ledger, one document per plan whose
``## Changes`` rows each lead with a Step id. This checker reads every
ledger through the shared row parser, resolves its parent plan, and
classifies each covered Step against the plan's live, retired, and checked
Step ids. It then walks every live plan and reports each closed Step the
ledger has no row for.

Findings, by severity:

- ``ERROR``: a per-Step execution record (a non-ledger ``exec`` document
  carrying ``step_id:``). The scaffolder no longer produces one; the fix is
  ``vault exec fold``. Also ``ERROR``: a closed Step with no ledger row when
  the plan's ledger already carries a verb-written row (anything but the
  fold's ``T``), because execution under that plan is being logged and this
  Step was closed without evidence.
- ``WARNING``: a closed Step with no row when the plan has no ledger yet, or
  only a ledger folded from history (all ``T`` rows), both legacy states; a
  ledger row for a Step that is still open; a row naming a Step the plan
  never had; a ledger whose parent plan is missing or unparseable.
- Clean: a row naming a retired Step. Ledger rows are history; the Step ran
  before it was retired and the row is the evidence.

An archived parent plan (``.vault/_archive/plan/``) is the expected steady
state and produces no finding. An ``exec`` document with neither a ledger
stem nor ``step_id:`` cannot be attributed to a Step and is skipped. The
checker is read-only: the remedy is named in each finding, never applied.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ..exec_ledger import (
    MIGRATED_OP,
    is_ledger_stem,
    ledger_step_ids,
    parse_ledger_rows,
)
from ._base import CheckDiagnostic, CheckResult, Severity, extract_feature_tags

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from ._base import VaultSnapshot

logger = logging.getLogger(__name__)

__all__ = ["check_exec_mapping", "link_stem"]

#: Strip the ``[[`` / ``]]`` wrapper (and any ``#anchor`` / ``|alias``) from a
#: ``related:`` wiki-link, yielding the bare document stem.
_WIKILINK_RE = re.compile(r"^\[\[([^\]#|]+)")

#: The three Step-id sets a parsed plan yields: live, retired, checked.
_PlanIds = tuple[set[str], set[str], set[str]]


def link_stem(link: str) -> str | None:
    """Return the bare document stem from a ``[[wiki-link]]`` string."""
    match = _WIKILINK_RE.match(link.strip())
    if match:
        return match.group(1).strip()
    return None


def check_exec_mapping(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
    raw_texts: Mapping[Path, tuple[str, bool]] | None = None,
) -> CheckResult:
    """Validate every ledger row and every closed Step against each other.

    Per-plan work is memoized for the whole pass: each distinct parent plan
    is parsed exactly once no matter how many documents reference it,
    live-plan existence is answered from the snapshot's own key set instead
    of a disk probe per record, and archive probes are cached per stem. With
    *raw_texts* supplied, plan parsing consumes the ingress read's text and
    the calculate phase touches the corpus on disk not at all.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed
            ``(metadata, body)`` tuples.
        feature: Restrict checks to documents carrying this feature tag
            (without ``#``).
        raw_texts: The ingress read's per-document ``(text, crlf)`` map (see
            :attr:`~vaultspec_core.graph.api.VaultGraph.raw_texts`); when
            supplied, parent plans are parsed from it rather than from disk.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with check
        name ``"exec-mapping"``. Does not support ``--fix``.
    """
    from ...config import get_config
    from ..models import DocType
    from ..scanner import get_doc_type

    result = CheckResult(check_name="exec-mapping", supports_fix=False)

    docs_dir = root_dir / get_config().docs_dir
    plan_dir = docs_dir / "plan"
    archive_plan_dir = docs_dir / "_archive" / "plan"
    wanted = feature.lstrip("#") if feature else None

    live_plan_names = {p.name for p in snapshot if p.parent == plan_dir}
    archived_stem_cache: dict[str, bool] = {}
    plan_ids_cache: dict[Path, _PlanIds | Exception] = {}
    #: Step ids each live plan has evidence for, from ledgers and per-Step
    #: records alike, so a closed Step is never reported missing twice over.
    covered: dict[Path, set[str]] = {}
    #: Live plans whose ledger carries a verb-written row: execution there is
    #: being logged, so a closed Step without a row is an error, not legacy
    #: drift. A ledger folded from history carries only ``T`` rows and does
    #: not qualify.
    ledger_plans: set[Path] = set()

    for doc_path, (metadata, body) in sorted(snapshot.items()):
        if get_doc_type(doc_path, root_dir) is not DocType.EXEC:
            continue
        if wanted and wanted not in extract_feature_tags(metadata.tags):
            continue

        rel_path = doc_path.relative_to(root_dir)
        candidate_stems = [
            stem for link in metadata.related if (stem := link_stem(link))
        ]
        live_plan_path, archived = _resolve_parent_plan(
            candidate_stems,
            plan_dir=plan_dir,
            live_plan_names=live_plan_names,
            archive_plan_dir=archive_plan_dir,
            archived_stem_cache=archived_stem_cache,
        )

        if is_ledger_stem(doc_path.stem):
            step_ids = ledger_step_ids(body)
            if live_plan_path is not None and _has_native_row(body):
                ledger_plans.add(live_plan_path)
        elif metadata.step_id:
            step_ids = (metadata.step_id,)
            result.diagnostics.append(
                _per_step_record_diagnostic(rel_path, metadata.tags)
            )
        else:
            step_ids = ()

        if not step_ids:
            # Legacy record predating the step_id field, or a ledger naming
            # no Step: unmappable, not a defect. Skipped without a finding.
            continue

        if live_plan_path is None:
            if archived:
                continue
            result.diagnostics.append(
                _missing_plan_diagnostic(rel_path, step_ids[0], candidate_stems)
            )
            continue

        covered.setdefault(live_plan_path, set()).update(step_ids)
        if not is_ledger_stem(doc_path.stem):
            # The per-Step record's own error is the finding; its Step
            # mapping is not classified a second time.
            continue

        ids_or_error = _resolve_step_ids(
            live_plan_path, raw_texts=raw_texts, cache=plan_ids_cache
        )
        if isinstance(ids_or_error, Exception):
            result.diagnostics.append(
                _unparseable_plan_diagnostic(
                    live_plan_path, root_dir, step_ids[0], ids_or_error
                )
            )
            continue

        live_ids, retired_ids, checked_ids = ids_or_error
        for covered_step_id in step_ids:
            diagnostic = _row_diagnostic(
                rel_path,
                covered_step_id,
                live_plan_path,
                live_ids=live_ids,
                retired_ids=retired_ids,
                checked_ids=checked_ids,
            )
            if diagnostic is not None:
                result.diagnostics.append(diagnostic)

    for plan_path, (metadata, _body) in sorted(snapshot.items()):
        if plan_path.parent != plan_dir:
            continue
        if wanted and wanted not in extract_feature_tags(metadata.tags):
            continue
        ids_or_error = _resolve_step_ids(
            plan_path, raw_texts=raw_texts, cache=plan_ids_cache
        )
        if isinstance(ids_or_error, Exception):
            # Reported above when a ledger references it; a plan nobody
            # executes yet is the structure check's concern, not this one's.
            continue
        _live, _retired, checked_ids = ids_or_error
        missing = sorted(checked_ids - covered.get(plan_path, set()))
        if missing:
            result.diagnostics.append(
                _missing_rows_diagnostic(
                    plan_path.relative_to(root_dir),
                    missing,
                    has_ledger=plan_path in ledger_plans,
                )
            )

    return result


def _has_native_row(body: str) -> bool:
    """Whether a ledger body carries any row ``vault exec log`` wrote.

    A fold recovers ``T`` rows only; the first natively logged row (``A``,
    ``M``, ``D``, ``R``, ``verify:``, ``by:``) marks the plan as one whose
    execution is being logged.
    """
    return any(
        row.step_id is not None and (row.label is not None or row.op != MIGRATED_OP)
        for row in parse_ledger_rows(body)
    )


def _is_archived_stem(
    stem: str, archive_plan_dir: Path, cache: dict[str, bool]
) -> bool:
    """Return whether *stem* names a plan under ``.vault/_archive/plan/``.

    Probes are memoized per stem so a stem referenced by many exec records
    costs one disk check for the whole pass.
    """
    cached = cache.get(stem)
    if cached is None:
        cached = (archive_plan_dir / f"{stem}.md").is_file()
        cache[stem] = cached
    return cached


def _resolve_parent_plan(
    candidate_stems: list[str],
    *,
    plan_dir: Path,
    live_plan_names: set[str],
    archive_plan_dir: Path,
    archived_stem_cache: dict[str, bool],
) -> tuple[Path | None, bool]:
    """Resolve an exec document's parent plan from its candidate stems.

    The first candidate stem resolving to a live plan wins. Failing that, the
    remaining stems are still probed against the archive so the caller can
    tell "the parent is archived" (benign) apart from "no parent exists at
    all" (a defect).

    Returns:
        A ``(live_plan_path, archived)`` pair: *live_plan_path* is ``None``
        when no candidate stem names a live plan, and *archived* is ``True``
        when, in that case, some candidate stem names an archived plan.
    """
    archived = False
    for stem in candidate_stems:
        if f"{stem}.md" in live_plan_names:
            return plan_dir / f"{stem}.md", False
        if not archived and _is_archived_stem(
            stem, archive_plan_dir, archived_stem_cache
        ):
            archived = True
    return None, archived


def _resolve_step_ids(
    plan_path: Path,
    *,
    raw_texts: Mapping[Path, tuple[str, bool]] | None,
    cache: dict[Path, _PlanIds | Exception],
) -> _PlanIds | Exception:
    """Return the memoized (live, retired, checked) Step id sets for a plan.

    With *raw_texts* supplied, the plan is parsed from the ingress read's
    text rather than from disk; a plan present in the corpus whose text never
    survived ingress is classified as unparseable, matching what a disk read
    of an unreadable file would conclude anyway.
    """
    cached = cache.get(plan_path)
    if cached is not None:
        return cached

    source: str | Path = plan_path
    if raw_texts is not None:
        entry = raw_texts.get(plan_path)
        if entry is None:
            error: _PlanIds | Exception = ValueError(
                "plan document could not be read during ingress"
            )
            cache[plan_path] = error
            return error
        source = entry[0]

    try:
        resolved: _PlanIds | Exception = _plan_step_ids(source)
    except Exception as exc:
        resolved = exc
    cache[plan_path] = resolved
    return resolved


def _per_step_record_diagnostic(rel_path: Path, tags: list[str]) -> CheckDiagnostic:
    """Build the ERROR for a per-Step execution record."""
    features = extract_feature_tags(tags)
    feature = features[0] if features else "<feature>"
    return CheckDiagnostic(
        path=rel_path,
        message=(
            "Per-Step execution record: execution is logged with "
            "`vault exec log`, and the ledger is the only execution artifact."
        ),
        severity=Severity.ERROR,
        fixable=False,
        fix_description=(
            f"Fold it into the plan's ledger: "
            f"`vaultspec-core vault exec fold --feature {feature} --force`."
        ),
    )


def _missing_plan_diagnostic(
    rel_path: Path, step_id: str, candidate_stems: list[str]
) -> CheckDiagnostic:
    """Build the WARNING for an exec document whose parent plan is not found."""
    plan_hint = next((s for s in candidate_stems if s.endswith("-plan")), None)
    named = f" '{plan_hint}'" if plan_hint else ""
    return CheckDiagnostic(
        path=rel_path,
        message=(
            f"Execution record declares step {step_id} but its "
            f"parent plan{named} was not found in .vault/plan/ or "
            ".vault/_archive/plan/."
        ),
        severity=Severity.WARNING,
        fixable=False,
        fix_description=(
            "Point related: at the correct parent plan, or archive "
            "the record if its plan is gone."
        ),
    )


def _unparseable_plan_diagnostic(
    live_plan_path: Path, root_dir: Path, step_id: str, exc: Exception
) -> CheckDiagnostic:
    """Build the WARNING for a parent plan that failed to parse."""
    logger.debug("Could not parse plan %s: %s", live_plan_path, exc)
    return CheckDiagnostic(
        path=live_plan_path.relative_to(root_dir),
        message=(
            "Parent plan could not be parsed, so the execution "
            f"record for step {step_id} cannot be verified: {exc}"
        ),
        severity=Severity.WARNING,
        fixable=False,
        fix_description="Repair the plan document structure.",
    )


def _row_diagnostic(
    rel_path: Path,
    step_id: str,
    live_plan_path: Path,
    *,
    live_ids: set[str],
    retired_ids: set[str],
    checked_ids: set[str],
) -> CheckDiagnostic | None:
    """Classify one ledger Step against the parent plan's Step sets.

    Returns ``None`` when the Step is live and closed, or retired (its rows
    are history); a WARNING when the Step is live but still open, or when
    the plan never had it.
    """
    if step_id in retired_ids:
        return None
    if step_id in live_ids:
        if step_id in checked_ids:
            return None
        return CheckDiagnostic(
            path=rel_path,
            message=(
                f"Ledger has rows for Step {step_id}, which is still open in "
                f"'{live_plan_path.stem}'."
            ),
            severity=Severity.WARNING,
            fixable=False,
            fix_description=(
                "Close the Step with `vaultspec-core vault plan step check` "
                "once its checks pass, or reopen the work the rows describe."
            ),
        )
    return CheckDiagnostic(
        path=rel_path,
        message=(
            f"Ledger row names Step {step_id}, which does not exist in "
            f"parent plan '{live_plan_path.stem}'."
        ),
        severity=Severity.WARNING,
        fixable=False,
        fix_description="Log the rows again under a Step that exists in the plan.",
    )


def _missing_rows_diagnostic(
    rel_path: Path, missing: list[str], *, has_ledger: bool
) -> CheckDiagnostic:
    """Build the finding for closed Steps the ledger has no row for."""
    listed = ", ".join(missing)
    return CheckDiagnostic(
        path=rel_path,
        message=(
            f"Closed Step(s) with no ledger row: {listed}. "
            + (
                "The plan's ledger is being written, so these were closed "
                "without evidence."
                if has_ledger
                else "The plan has no logged ledger yet."
            )
        ),
        severity=Severity.ERROR if has_ledger else Severity.WARNING,
        fixable=False,
        fix_description=(
            "Log each Step: `vaultspec-core vault exec log --feature <feature> "
            "--step S## --related <plan-stem> --row M:path`."
        ),
    )


def _plan_step_ids(source: str | Path) -> _PlanIds:
    """Return the (live, retired, checked) canonical Step id sets for a plan.

    *source* is either the plan's path (read from disk) or its full text
    (the ingress read's copy); ``parse_plan`` accepts both.
    """
    from ...plan.parser import parse_plan

    plan = parse_plan(source)
    live = {step.canonical_id for step in plan.steps}
    checked = {step.canonical_id for step in plan.steps if step.checked}
    return live, set(plan.retired_step_ids), checked
