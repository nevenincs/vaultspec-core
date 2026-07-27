"""Back-map every execution record to a live Step in its parent plan.

An execution record carries a ``step_id`` frontmatter stamp and a
``related:`` wiki-link to its parent plan. Nothing previously confirmed that
the referenced Step still exists: a retired id, a renamed or deleted plan, or
a typo left the record pointing at nothing while every check reported clean.

This checker resolves each exec record's parent plan and classifies its
``step_id`` against the plan's live and retired Step ids:

- ``step_id`` present in the plan's live Step ids -> clean.
- ``step_id`` present only in the plan's retired ledger -> WARNING (the Step
  was removed; the record is orphaned).
- ``step_id`` absent from both -> WARNING (dangling Step id).
- The parent plan is not found in ``.vault/plan/`` -> before flagging, the
  ``.vault/_archive/plan/`` tree is probed: an archived parent is the expected,
  benign steady state and produces no finding, while a truly-absent parent is a
  WARNING.
- The parent plan cannot be parsed -> a single WARNING against that plan rather
  than a crash (No-Crash policy).

A legacy exec record that carries no ``step_id`` (predating the field) cannot
be back-mapped and is skipped, not flagged. The checker is read-only: no
dangling reference has an unambiguous automatic repair, so each finding's
``fix_description`` names the manual remedy instead.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ._base import CheckDiagnostic, CheckResult, Severity, extract_feature_tags

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from ._base import VaultSnapshot

logger = logging.getLogger(__name__)

__all__ = ["check_exec_mapping"]

#: Strip the ``[[`` / ``]]`` wrapper (and any ``#anchor`` / ``|alias``) from a
#: ``related:`` wiki-link, yielding the bare document stem.
_WIKILINK_RE = re.compile(r"^\[\[([^\]#|]+)")


def _link_stem(link: str) -> str | None:
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
    """Validate every execution record maps to a live Step in its parent plan.

    Per-plan work is memoized for the whole pass: each distinct parent plan
    is parsed exactly once no matter how many records reference it, live-plan
    existence is answered from the snapshot's own key set instead of a disk
    probe per record, and archive probes are cached per stem. With
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

    # Live plans are exactly the snapshot documents inside the plan
    # directory: the snapshot's key set answers existence without a disk
    # probe per record. Archive probes and per-plan parses are memoized so
    # each distinct stem costs one lookup for the whole pass.
    live_plan_names = {p.name for p in snapshot if p.parent == plan_dir}
    archived_stem_cache: dict[str, bool] = {}
    plan_ids_cache: dict[Path, tuple[set[str], set[str]] | Exception] = {}

    def _is_archived(stem: str) -> bool:
        cached = archived_stem_cache.get(stem)
        if cached is None:
            cached = (archive_plan_dir / f"{stem}.md").is_file()
            archived_stem_cache[stem] = cached
        return cached

    def _step_ids(plan_path: Path) -> tuple[set[str], set[str]] | Exception:
        cached = plan_ids_cache.get(plan_path)
        if cached is None:
            source: str | Path = plan_path
            if raw_texts is not None:
                entry = raw_texts.get(plan_path)
                if entry is None:
                    # The plan is in the corpus but its text never survived
                    # ingress (read or decode failure). The single-ingress
                    # contract forbids a disk fallback, so classify it as
                    # unparseable - which a disk read of an unreadable file
                    # would conclude anyway.
                    cached = ValueError(
                        "plan document could not be read during ingress"
                    )
                    plan_ids_cache[plan_path] = cached
                    return cached
                source = entry[0]
            try:
                cached = _plan_step_ids(source)
            except Exception as exc:
                cached = exc
            plan_ids_cache[plan_path] = cached
        return cached

    for doc_path, (metadata, _body) in sorted(snapshot.items()):
        if get_doc_type(doc_path, root_dir) is not DocType.EXEC:
            continue
        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        step_id = metadata.step_id
        if not step_id:
            # Legacy record predating the step_id field: unmappable, not a
            # defect. Skipped without a finding.
            continue

        rel_path = doc_path.relative_to(root_dir)

        # Resolve the parent plan from the record's related wiki-links. The
        # first link resolving to a live plan wins; failing that, an archived
        # plan is recognised as the expected steady state.
        candidate_stems = [
            stem for link in metadata.related if (stem := _link_stem(link))
        ]
        live_plan_path: Path | None = None
        archived_stem: str | None = None
        for stem in candidate_stems:
            if f"{stem}.md" in live_plan_names:
                live_plan_path = plan_dir / f"{stem}.md"
                break
            if _is_archived(stem):
                archived_stem = stem

        if live_plan_path is None:
            if archived_stem is not None:
                # Archived parent plan: expected and benign. No finding.
                continue
            plan_hint = next((s for s in candidate_stems if s.endswith("-plan")), None)
            named = f" '{plan_hint}'" if plan_hint else ""
            result.diagnostics.append(
                CheckDiagnostic(
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
            )
            continue

        ids_or_error = _step_ids(live_plan_path)
        if isinstance(ids_or_error, Exception):
            exc = ids_or_error
            logger.debug("Could not parse plan %s: %s", live_plan_path, exc)
            result.diagnostics.append(
                CheckDiagnostic(
                    path=live_plan_path.relative_to(root_dir),
                    message=(
                        "Parent plan could not be parsed, so the execution "
                        f"record for step {step_id} cannot be verified: {exc}"
                    ),
                    severity=Severity.WARNING,
                    fixable=False,
                    fix_description="Repair the plan document structure.",
                )
            )
            continue

        live_ids, retired_ids = ids_or_error
        if step_id in live_ids:
            continue
        if step_id in retired_ids:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"Execution record references retired Step {step_id}: "
                        f"the Step was removed from '{live_plan_path.stem}' and "
                        "its id is never reused."
                    ),
                    severity=Severity.WARNING,
                    fixable=False,
                    fix_description=(
                        "Re-point the record at a live Step, or retire the "
                        "record alongside its Step."
                    ),
                )
            )
            continue

        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=(
                    f"Execution record declares Step {step_id}, which does not "
                    f"exist in parent plan '{live_plan_path.stem}'."
                ),
                severity=Severity.WARNING,
                fixable=False,
                fix_description=(
                    "Correct the step_id to a Step that exists in the parent plan."
                ),
            )
        )

    return result


def _plan_step_ids(source: str | Path) -> tuple[set[str], set[str]]:
    """Return the (live, retired) canonical Step id sets for a plan.

    *source* is either the plan's path (read from disk) or its full text
    (the ingress read's copy); ``parse_plan`` accepts both.
    """
    from ...plan.parser import parse_plan

    plan = parse_plan(source)
    live = {step.canonical_id for step in plan.steps}
    return live, set(plan.retired_step_ids)
