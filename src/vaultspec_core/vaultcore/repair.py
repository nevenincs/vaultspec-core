"""Repair pipeline orchestration for vault content recovery.

The repair pipeline is intentionally separate from individual checkers:
``vault check all --fix`` remains a check-level compatibility surface,
while this module models an operator recovery run with preflight,
diagnosis, optional mutation, generated-index refresh, and postcheck
phases.
"""

from __future__ import annotations

import pathlib
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from ..migrations import MigrationStatus, migration_status, run_pending_migrations
from .checks import CheckDiagnostic, CheckResult, Severity, run_all_checks

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

__all__ = [
    "RepairPhase",
    "RepairRun",
    "run_repair_pipeline",
]


class RepairPhase(StrEnum):
    """Named phases emitted by ``vaultspec-core vault repair``."""

    PREFLIGHT = "preflight"
    CHECK = "check"
    FIX = "fix"
    INDEX = "index"
    POSTCHECK = "postcheck"
    SUMMARY = "summary"


@dataclass
class RepairRun:
    """Structured result from a vault repair pipeline run."""

    dry_run: bool
    feature: str | None = None
    include_index: bool = True
    partial_failure: bool = False
    phases: list[dict[str, Any]] = field(default_factory=list)
    journal: list[dict[str, Any]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    generated_indexes: list[str] = field(default_factory=list)
    planned_fixes: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    root_causes: list[dict[str, Any]] = field(default_factory=list)
    postcheck: list[CheckResult] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Number of postcheck ERROR diagnostics."""
        return sum(result.error_count for result in self.postcheck) + int(
            self.partial_failure
        )

    @property
    def warning_count(self) -> int:
        """Number of postcheck WARNING diagnostics."""
        return sum(result.warning_count for result in self.postcheck)

    @property
    def fixed_count(self) -> int:
        """Total fixes applied by the mutating check pass."""
        return sum(
            int(phase.get("fixed_count", 0))
            for phase in self.phases
            if phase.get("phase") == RepairPhase.FIX.value
        )


def run_repair_pipeline(
    root_dir: Path,
    *,
    dry_run: bool = False,
    include_index: bool = True,
    feature: str | None = None,
) -> RepairRun:
    """Run the vault repair pipeline.

    Args:
        root_dir: Project root directory.
        dry_run: Preview intended changes without mutating files.
        include_index: Rebuild generated feature indexes after fixes.
        feature: Optional feature tag scope, without or with leading ``#``.

    Returns:
        :class:`RepairRun` with per-phase details and postcheck results.
    """
    feat = feature.lstrip("#") if feature else None
    run = RepairRun(dry_run=dry_run, feature=feat, include_index=include_index)
    before = _vault_file_fingerprints(root_dir)

    try:
        status, pending_names = migration_status(root_dir)
    except Exception as exc:
        run = RepairRun(dry_run=dry_run, feature=feat, include_index=include_index)
        _record_failure(run, RepairPhase.PREFLIGHT, exc)
        run.phases.append(
            {
                "phase": RepairPhase.PREFLIGHT.value,
                "migration_status": "unknown",
                "pending_migrations": [],
                "platform": _platform_summary(root_dir),
                "applied_migrations": [],
                "skipped": False,
                "failed": True,
                "error": str(exc),
            }
        )
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run
    preflight: dict[str, Any] = {
        "phase": RepairPhase.PREFLIGHT.value,
        "migration_status": status.value,
        "pending_migrations": pending_names,
        "platform": _platform_summary(root_dir),
        "applied_migrations": [],
        "skipped": False,
    }
    if dry_run and status == MigrationStatus.PENDING:
        preflight["skipped"] = True
        preflight["message"] = (
            "Dry-run skipped vault scanning because pending migrations would "
            "mutate the workspace on first use."
        )
        run.phases.append(preflight)
        run.postcheck = []
        run.unresolved.append(
            {
                "severity": Severity.WARNING.value,
                "check": RepairPhase.PREFLIGHT.value,
                "message": "Run vaultspec-core migrations run before repair dry-run.",
                "path": None,
            }
        )
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run

    if not dry_run:
        try:
            applied = run_pending_migrations(root_dir)
        except Exception as exc:
            _record_failure(run, RepairPhase.PREFLIGHT, exc)
            preflight["failed"] = True
            preflight["error"] = str(exc)
            run.phases.append(preflight)
            _finalize(run, before, _vault_file_fingerprints(root_dir))
            return run
        preflight["applied_migrations"] = [
            {
                "name": result.name,
                "target_version": result.target_version,
                "summary": result.summary,
                "counts": result.counts,
            }
            for result in applied
        ]
    run.phases.append(preflight)

    try:
        initial = run_all_checks(root_dir, feature=feat, fix=False)
    except Exception as exc:
        _record_failure(run, RepairPhase.CHECK, exc)
        run.phases.append(_failed_phase(RepairPhase.CHECK, exc))
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run
    run.phases.append(_checks_phase(RepairPhase.CHECK, initial))
    run.planned_fixes = _collect_fixable(initial)
    run.root_causes = _group_root_causes(initial)

    if dry_run:
        for item in run.planned_fixes:
            _record_journal(
                run,
                RepairPhase.FIX,
                action="planned-fix",
                status="planned",
                path=item.get("path"),
                check=item.get("check"),
                message=item.get("fix_description") or item.get("message"),
            )
        run.phases.append(
            {
                "phase": RepairPhase.FIX.value,
                "dry_run": True,
                "fixed_count": 0,
                "planned_count": len(run.planned_fixes),
                "skipped": False,
            }
        )
        if include_index:
            planned_indexes = _index_paths(root_dir, feat)
            run.generated_indexes = [_rel_str(p, root_dir) for p in planned_indexes]
            for path in run.generated_indexes:
                _record_journal(
                    run,
                    RepairPhase.INDEX,
                    action="refresh-index",
                    status="planned",
                    path=path,
                )
            run.phases.append(
                {
                    "phase": RepairPhase.INDEX.value,
                    "dry_run": True,
                    "planned": run.generated_indexes,
                    "generated": [],
                    "skipped": False,
                }
            )
        else:
            run.phases.append(_skipped_index_phase("disabled by --no-index"))
        run.postcheck = initial
        run.phases.append(_checks_phase(RepairPhase.POSTCHECK, initial, dry_run=True))
        run.unresolved = _collect_unresolved(initial)
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run

    phase_before = _vault_file_fingerprints(root_dir)
    try:
        fixed = run_all_checks(root_dir, feature=feat, fix=True)
    except Exception as exc:
        _record_failure(run, RepairPhase.FIX, exc)
        run.phases.append(_failed_phase(RepairPhase.FIX, exc))
        _record_file_deltas(
            run,
            RepairPhase.FIX,
            phase_before,
            _vault_file_fingerprints(root_dir),
        )
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run
    run.phases.append(_checks_phase(RepairPhase.FIX, fixed))
    _record_file_deltas(
        run,
        RepairPhase.FIX,
        phase_before,
        _vault_file_fingerprints(root_dir),
    )

    if include_index:
        phase_before = _vault_file_fingerprints(root_dir)
        try:
            generated = _refresh_indexes(root_dir, feat)
        except Exception as exc:
            _record_failure(run, RepairPhase.INDEX, exc)
            run.phases.append(
                {
                    "phase": RepairPhase.INDEX.value,
                    "dry_run": False,
                    "generated": [],
                    "skipped": False,
                    "failed": True,
                    "error": str(exc),
                }
            )
            _record_file_deltas(
                run,
                RepairPhase.INDEX,
                phase_before,
                _vault_file_fingerprints(root_dir),
            )
            failure_unresolved = list(run.unresolved)
            try:
                postcheck = run_all_checks(root_dir, feature=feat, fix=False)
            except Exception as postcheck_exc:
                _record_failure(run, RepairPhase.POSTCHECK, postcheck_exc)
                run.phases.append(_failed_phase(RepairPhase.POSTCHECK, postcheck_exc))
                _finalize(run, before, _vault_file_fingerprints(root_dir))
                return run
            run.postcheck = postcheck
            run.unresolved = failure_unresolved + _collect_unresolved(postcheck)
            run.root_causes = _group_root_causes(postcheck)
            run.phases.append(_checks_phase(RepairPhase.POSTCHECK, postcheck))
            _finalize(run, before, _vault_file_fingerprints(root_dir))
            return run
        run.generated_indexes = [_rel_str(path, root_dir) for path in generated]
        run.phases.append(
            {
                "phase": RepairPhase.INDEX.value,
                "dry_run": False,
                "generated": run.generated_indexes,
                "skipped": False,
            }
        )
        _record_file_deltas(
            run,
            RepairPhase.INDEX,
            phase_before,
            _vault_file_fingerprints(root_dir),
        )
    else:
        run.phases.append(_skipped_index_phase("disabled by --no-index"))

    try:
        postcheck = run_all_checks(root_dir, feature=feat, fix=False)
    except Exception as exc:
        _record_failure(run, RepairPhase.POSTCHECK, exc)
        run.phases.append(_failed_phase(RepairPhase.POSTCHECK, exc))
        _finalize(run, before, _vault_file_fingerprints(root_dir))
        return run
    run.postcheck = postcheck
    run.unresolved = _collect_unresolved(postcheck)
    run.root_causes = _group_root_causes(postcheck)
    run.phases.append(_checks_phase(RepairPhase.POSTCHECK, postcheck))

    _finalize(run, before, _vault_file_fingerprints(root_dir))
    return run


def _checks_phase(
    phase: RepairPhase,
    results: list[CheckResult],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return {
        "phase": phase.value,
        "dry_run": dry_run,
        "checks": [_result_summary(result) for result in results],
        "error_count": sum(result.error_count for result in results),
        "warning_count": sum(result.warning_count for result in results),
        "info_count": sum(result.info_count for result in results),
        "fixed_count": sum(result.fixed_count for result in results),
    }


def _result_summary(result: CheckResult) -> dict[str, Any]:
    return {
        "check_name": result.check_name,
        "errors": result.error_count,
        "warnings": result.warning_count,
        "info": result.info_count,
        "fixed_count": result.fixed_count,
        "supports_fix": result.supports_fix,
        "diagnostics": [
            _diagnostic_payload(result.check_name, d) for d in result.diagnostics
        ],
    }


def _diagnostic_payload(check_name: str, diag: CheckDiagnostic) -> dict[str, Any]:
    return {
        "check": check_name,
        "path": str(diag.path) if diag.path is not None else None,
        "message": diag.message,
        "severity": diag.severity.value,
        "fixable": diag.fixable,
        "fix_description": diag.fix_description,
    }


def _failed_phase(phase: RepairPhase, exc: Exception) -> dict[str, Any]:
    return {
        "phase": phase.value,
        "dry_run": False,
        "failed": True,
        "error_count": 1,
        "warning_count": 0,
        "info_count": 0,
        "fixed_count": 0,
        "error": str(exc),
    }


def _record_failure(run: RepairRun, phase: RepairPhase, exc: Exception) -> None:
    run.partial_failure = True
    message = f"{phase.value} phase failed: {exc}"
    run.unresolved.append(
        {
            "severity": Severity.ERROR.value,
            "check": phase.value,
            "message": message,
            "path": None,
            "fixable": False,
            "fix_description": None,
        }
    )
    _record_journal(
        run,
        phase,
        action="phase",
        status="failed",
        message=message,
    )


def _record_journal(
    run: RepairRun,
    phase: RepairPhase,
    *,
    action: str,
    status: str,
    path: str | None = None,
    check: str | None = None,
    message: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "phase": phase.value,
        "action": action,
        "status": status,
    }
    if path is not None:
        entry["path"] = path
    if check is not None:
        entry["check"] = check
    if message is not None:
        entry["message"] = message
    run.journal.append(entry)


def _collect_fixable(results: Iterable[CheckResult]) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for result in results:
        for diag in result.diagnostics:
            if diag.fixable:
                planned.append(_diagnostic_payload(result.check_name, diag))
    return planned


def _collect_unresolved(results: Iterable[CheckResult]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for result in results:
        for diag in result.diagnostics:
            unresolved.append(_diagnostic_payload(result.check_name, diag))
    return unresolved


def _group_root_causes(results: Iterable[CheckResult]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "structure-and-naming": [],
        "link-integrity": [],
        "generated-index-lifecycle": [],
        "authorial-traceability": [],
        "frontmatter-style": [],
    }
    for result in results:
        for diag in result.diagnostics:
            payload = _diagnostic_payload(result.check_name, diag)
            message = diag.message.lower()
            if result.check_name == "structure" or "case" in message:
                buckets["structure-and-naming"].append(payload)
            elif result.check_name in {"references", "schema"} or any(
                token in message for token in ("adr", "research", "plan")
            ):
                buckets["authorial-traceability"].append(payload)
            elif "index" in message or result.check_name == "features":
                buckets["generated-index-lifecycle"].append(payload)
            elif result.check_name in {"links", "dangling", "body-links", "orphans"}:
                buckets["link-integrity"].append(payload)
            else:
                buckets["frontmatter-style"].append(payload)

    return [
        {"root_cause": name, "count": len(items), "diagnostics": items}
        for name, items in buckets.items()
        if items
    ]


def _refresh_indexes(root_dir: Path, feature: str | None) -> list[Path]:
    from ..graph import VaultGraph
    from .index import generate_feature_index

    graph = VaultGraph(root_dir)
    features = [feature] if feature else graph.get_features()
    generated: list[Path] = []
    for feat in features:
        nodes = graph.get_feature_nodes(feat)
        if not nodes:
            continue
        generated.append(generate_feature_index(root_dir, feat, nodes=nodes))
    return generated


def _index_paths(root_dir: Path, feature: str | None) -> list[Path]:
    from ..config import get_config
    from ..graph import VaultGraph

    cfg = get_config()
    index_dir = root_dir / cfg.docs_dir / cfg.index_dir
    graph = VaultGraph(root_dir)
    if feature:
        features = [feature] if graph.get_feature_nodes(feature) else []
    else:
        features = graph.get_features()
    return [index_dir / f"{feat}.index.md" for feat in features if feat]


def _skipped_index_phase(reason: str) -> dict[str, Any]:
    return {
        "phase": RepairPhase.INDEX.value,
        "skipped": True,
        "reason": reason,
        "generated": [],
    }


def _record_file_deltas(
    run: RepairRun,
    phase: RepairPhase,
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> None:
    for path in sorted(set(before) | set(after)):
        old = before.get(path)
        new = after.get(path)
        if old == new:
            continue
        if old is None:
            action = "create"
        elif new is None:
            action = "delete"
        else:
            action = "modify"
        _record_journal(
            run,
            phase,
            action=action,
            status="applied",
            path=path,
        )


def _finalize(
    run: RepairRun,
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> None:
    run.changed_files = _changed_files(before, after)
    run.phases.append(
        {
            "phase": RepairPhase.SUMMARY.value,
            "dry_run": run.dry_run,
            "changed_files": run.changed_files,
            "generated_indexes": run.generated_indexes,
            "unresolved_count": len(run.unresolved),
            "partial_failure": run.partial_failure,
            "journal_count": len(run.journal),
            "root_causes": [
                {"root_cause": item["root_cause"], "count": item["count"]}
                for item in run.root_causes
            ],
        }
    )


def _vault_file_fingerprints(root_dir: Path) -> dict[str, tuple[int, int]]:
    from ..config import get_config

    docs_dir = root_dir / get_config().docs_dir
    if not docs_dir.is_dir():
        return {}
    fingerprints: dict[str, tuple[int, int]] = {}
    for path in sorted(docs_dir.rglob("*.md")):
        try:
            rel = _rel_str(path, root_dir)
        except ValueError:
            rel = str(path)
        try:
            stat = path.stat()
            fingerprints[rel] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            continue
    return fingerprints


def _changed_files(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> list[str]:
    paths = sorted(set(before) | set(after))
    return [path for path in paths if before.get(path) != after.get(path)]


def _platform_summary(root_dir: Path) -> dict[str, Any]:
    return {
        "case_sensitive_probe": _case_sensitive_probe(root_dir),
    }


def _case_sensitive_probe(root_dir: Path) -> str:
    try:
        probe = tempfile.TemporaryDirectory(
            prefix=".vaultspec-repair-probe-",
            dir=root_dir,
        )
    except OSError:
        return "unknown"
    with probe as probe_dir_name:
        probe_dir = pathlib.Path(probe_dir_name)
        lower = probe_dir / "case-probe.tmp"
        upper = probe_dir / "CASE-PROBE.tmp"
        try:
            lower.write_text("probe", encoding="utf-8")
            if upper.exists() and lower.resolve() == upper.resolve():
                return "case_insensitive"
            return "case_sensitive" if not upper.exists() else "case_insensitive"
        except OSError:
            return "unknown"


def _rel_str(path: Path, root_dir: Path) -> str:
    try:
        return path.relative_to(root_dir).as_posix()
    except ValueError:
        return path.as_posix()
