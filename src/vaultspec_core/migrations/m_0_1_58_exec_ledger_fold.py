"""Fold per-Step execution records into one consolidated ledger per plan.

Introduced for vaultspec-core 0.1.58 as the data counterpart of the
exec-record-consolidation ADR. A ``body-v1`` corpus stores one document per
plan Step, which on the measured production vault is 7,362 files and 17.9 MB
- 38% of the vault by bytes and 66% of its files - of which 83.8% is prose no
consumer reads. This migration folds each plan's records into a single
append-only ledger, recovering the machine-usable content and discarding the
prose.

Unlike every migration before it, this one **removes documents**. That is the
schema change: consolidation is not expressible as an additive rewrite. The
removal is ordered so it cannot lose data - the ledger carrying a record's
content is written and flushed before that record is unlinked, so an
interruption leaves duplication rather than loss - and the discarded bodies
remain in the commit preceding the migration, because ``.vault/`` is tracked.
There is, however, no forward command that restores them.

The migration writes facts, not inferences. A recovered row carries the paths
the record's own ``## Scope`` section listed, which the scaffolder filled from
the originating Step row. It never states an operation:
``body-v1`` did not record whether a path was added, modified, or deleted, so
rows carry ``T`` (touched), which stays distinguishable from an operation an
executor actually reported.

Records that cannot be attributed to a single Step are left untouched: one
with no ``step_id``, and a Phase summary, which rolls up Steps rather than
documenting one. Folding either would drop evidence the ledger cannot carry.

Scope is deliberately narrow: only records declaring a pre-``body-v2``
schema fold. A current-schema per-Step record is a legitimate document, not
legacy shape, and consolidating it is the operator's call through
``vault exec fold``. This matters because the driver bumps the manifest to the
running package version rather than a migration's target, so a workspace on a
pre-release build re-runs the registry on every vault command - and a
migration that folded current records would silently eat freshly authored
ones.

Idempotent by construction: the planner refuses to fold a ledger into itself,
a folded corpus offers no per-Step records to fold, and anything written after
the fold declares the current schema, so a second run plans nothing and
touches no file.

See also:
    :mod:`vaultspec_core.migrations` for the registry driver.
    :mod:`vaultspec_core.vaultcore.exec_fold` for the pure fold planner.
    :mod:`vaultspec_core.vaultcore.exec_ledger` for the row grammar.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import TYPE_CHECKING, cast

from . import Migration, MigrationError, MigrationResult

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MIGRATION", "migrate"]

logger = logging.getLogger(__name__)

_TARGET_VERSION = "0.1.58"
_NAME = "exec_ledger_fold"


def _plan_stem_from(related: object, fallback: str) -> str:
    """Return the parent-plan stem named in *related*, or *fallback*."""
    from ..vaultcore.checks.exec_mapping import link_stem

    if not isinstance(related, list):
        return fallback
    # Frontmatter is untyped data, so the list is narrowed before iteration
    # rather than suppressed at the use site.
    links: tuple[object, ...] = tuple(cast("list[object]", related))
    for link in links:
        stem = link_stem(str(link))
        if stem and stem.endswith("-plan"):
            return stem
    return fallback


def migrate(workspace: Path) -> MigrationResult:
    """Fold every feature's per-Step execution records into one ledger each.

    Args:
        workspace: Workspace root directory.

    Returns:
        :class:`MigrationResult` whose ``counts`` carry ``folders`` (feature
        folders consolidated), ``folded`` (records removed), ``rows`` (ledger
        rows written), ``paths`` (scope paths recovered), and ``skipped``
        (records deliberately left intact).

    Raises:
        MigrationError: When a ledger cannot be written or a folded record
            cannot be removed. The driver propagates it unchanged so the
            manifest version is not bumped and the next invocation retries.
    """
    from ..config import get_config
    from ..core.helpers import atomic_write
    from ..vaultcore import parse_vault_metadata
    from ..vaultcore.body_schema import CURRENT_BODY_SCHEMA
    from ..vaultcore.exec_fold import plan_fold, sources_from
    from ..vaultcore.exec_ledger import append_rows
    from ..vaultcore.hydration import (
        DocumentIdentity,
        ExecBinding,
        ParentPlan,
        TemplateFields,
        WritePolicy,
        create_vault_doc,
    )
    from ..vaultcore.models import DocType, refresh_modified_stamp

    cfg = get_config()
    exec_dir = workspace / cfg.docs_dir / "exec"
    counts = {
        "folders": 0,
        "folded": 0,
        "rows": 0,
        "paths": 0,
        "skipped": 0,
        "current": 0,
    }
    if not exec_dir.is_dir():
        return MigrationResult(
            name=_NAME,
            target_version=_TARGET_VERSION,
            summary="no .vault/exec/ directory; nothing to fold",
            counts=counts,
        )

    for folder in sorted(item for item in exec_dir.iterdir() if item.is_dir()):
        records: list[tuple[Path, str | None, str]] = []
        plan_stem = f"{folder.name}-plan"
        feature = folder.name[11:] or folder.name

        for doc in sorted(folder.glob("*.md")):
            try:
                content = doc.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise MigrationError(f"{_NAME}: failed to read {doc}: {exc}") from exc
            metadata, body = parse_vault_metadata(content)
            plan_stem = _plan_stem_from(metadata.related, plan_stem)
            if metadata.body_schema == CURRENT_BODY_SCHEMA:
                # A current-schema per-Step record is a legitimate document,
                # not legacy shape. Folding it is the operator's call through
                # `vault exec fold`, never a migration's: the manifest bumps
                # to the running package version rather than this migration's
                # target, so a pre-release workspace re-runs the registry on
                # every vault command, and folding current records would make
                # that silently eat freshly authored ones.
                counts["current"] += 1
                continue
            records.append((doc, metadata.step_id, body))

        plan = plan_fold(sources_from(records))
        if plan.is_empty:
            counts["skipped"] += len(plan.skipped)
            continue

        parent = ParentPlan(date=folder.name[:10], stem=plan_stem)
        identity = DocumentIdentity(
            doc_type=DocType.EXEC, feature=feature, date=folder.name[:10]
        )
        binding = ExecBinding(plan=parent, ledger=True)

        try:
            ledger_path = create_vault_doc(
                workspace,
                identity,
                TemplateFields(),
                exec_binding=binding,
                write=WritePolicy(force=True, dry_run=True),
            )
            if not ledger_path.exists():
                create_vault_doc(
                    workspace,
                    identity,
                    TemplateFields(),
                    exec_binding=binding,
                    write=WritePolicy(force=False, dry_run=False),
                )
            text = ledger_path.read_text(encoding="utf-8")
            updated = append_rows(text, plan.rows)
            if updated != text:
                atomic_write(
                    ledger_path, refresh_modified_stamp(updated, _dt.date.today())
                )
        except (OSError, ValueError) as exc:
            raise MigrationError(
                f"{_NAME}: failed to write ledger for {folder.name}: {exc}"
            ) from exc

        # Unlink only after the ledger carrying this content is on disk, so an
        # interruption leaves duplication rather than loss.
        for doc in plan.folded:
            if doc == ledger_path:
                continue
            try:
                doc.unlink(missing_ok=True)
            except OSError as exc:
                raise MigrationError(
                    f"{_NAME}: failed to remove folded record {doc}: {exc}"
                ) from exc

        counts["folders"] += 1
        counts["folded"] += len(plan.folded)
        counts["rows"] += len(plan.rows)
        counts["paths"] += plan.recovered_paths
        counts["skipped"] += len(plan.skipped)
        logger.info(
            "Migration %s: folded %d record(s) of %s into %s",
            _NAME,
            len(plan.folded),
            folder.name,
            ledger_path.name,
        )

    folded = counts["folded"]
    if not folded:
        summary = "no per-Step execution records to fold"
    else:
        summary = (
            f"folded {folded} execution "
            f"{'record' if folded == 1 else 'records'} into "
            f"{counts['folders']} {'ledger' if counts['folders'] == 1 else 'ledgers'} "
            f"({counts['paths']} scope path(s) recovered)"
        )
    if counts["skipped"]:
        summary += f"; {counts['skipped']} left intact"
    if counts["current"]:
        summary += f"; {counts['current']} current-schema record(s) untouched"

    return MigrationResult(
        name=_NAME,
        target_version=_TARGET_VERSION,
        summary=summary,
        counts=counts,
    )


MIGRATION = Migration(
    target_version=_TARGET_VERSION,
    name=_NAME,
    migrate=migrate,
)
