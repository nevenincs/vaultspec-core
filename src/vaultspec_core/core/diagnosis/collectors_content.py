"""Managed-content drift collectors.

Assesses whether a provider's deployed rule files still match their source,
which projected files an adoption run would rewrite, and whether rule/skill/
agent naming stays consistent. All imports from ``core.*`` modules are
deferred inside function bodies to prevent import cycles.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .collectors_provider import _TOOL_DIR
from .signals import ContentSignal, RenameIntegritySignal

logger = logging.getLogger(__name__)


def collect_content_integrity(tool_value: str) -> dict[str, ContentSignal]:
    """Check content integrity of managed rule files for a provider.

    Verifies that each managed rule file exists at the provider's
    destination.

    Args:
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        Mapping of filename to
        :class:`~vaultspec_core.core.diagnosis.signals.ContentSignal`.
    """
    from ..enums import Tool
    from ..helpers import collect_md_resources
    from ..rules import transform_rule
    from ..sync import apply_file_sync
    from ..system import SYSTEM_BUILTIN_RULE
    from ..types import SyncResult, get_context

    tool = Tool(tool_value)
    result: dict[str, ContentSignal] = {}

    try:
        ctx = get_context()
        cfg = ctx.tool_configs.get(tool)
    except LookupError:
        return result

    if cfg is None or cfg.rules_dir is None:
        return result

    dest_dir = cfg.rules_dir
    source_dir = ctx.rules_src_dir

    # Content integrity is decided by the same comparator sync uses, not by
    # filename presence. The ambiguous-states resolver ADR specified that this
    # collector reuse the sync infrastructure and compare expected transformed
    # output against the actual destination; a prior name-only implementation
    # drifted from that, reporting a content-drifted file as CLEAN while sync
    # would rewrite it. We render each managed rule through the same
    # ``transform_rule`` the sync engine applies, then route it through
    # ``apply_file_sync`` in dry-run mode (no write) so the doctor's verdict and
    # sync's verdict come from one decision. Content drift now surfaces as
    # DIVERGED instead of a false CLEAN.
    #
    # Source rules are globbed read-only and reduced to their flat basename -
    # the same name the flat provider deployment carries. The recursive glob in
    # ``collect_md_resources`` discovers any project-authored source one level
    # down (#153) without the flattening side effect of ``collect_rules`` (the
    # doctor must not mutate the source tree).
    expected: dict[str, str] = {}
    if source_dir.is_dir():
        raw_sources = collect_md_resources(source_dir)
        for key, (_src_path, meta, body) in raw_sources.items():
            name = key.replace("\\", "/").rsplit("/", 1)[-1]
            expected[name] = transform_rule(tool, name, meta, body)

    dest_files: set[str] = set()
    if dest_dir.is_dir():
        dest_files = {f.name for f in dest_dir.glob("*.md")}

    # Files with a source: dry-run the canonical comparator and map its action.
    # [UNCHANGED] -> CLEAN, [UPDATE] -> DIVERGED, [ADD] (dest absent) -> MISSING.
    for name, content in expected.items():
        probe = SyncResult()
        action = apply_file_sync(probe, dest_dir / name, content, dry_run=True)
        if action == "[UNCHANGED]":
            result[name] = ContentSignal.CLEAN
        elif action == "[ADD]":
            result[name] = ContentSignal.MISSING
        else:  # [UPDATE]
            result[name] = ContentSignal.DIVERGED

    # Files only in destination: an orphan with no source (e.g. a retired
    # builtin's leftover deployment). The synthesized system rule has no source.
    for name in dest_files - set(expected):
        if name == SYSTEM_BUILTIN_RULE:
            continue  # Synthesized by system_sync(), not sourced
        result[name] = ContentSignal.STALE

    return result


def collect_divergent_projections(target: Path) -> list[str]:
    """Return projected provider files whose on-disk content differs from source.

    Used by the adoption path to name, before anything is written, the files an
    adopting run's provider sync would rewrite. The sync engine's per-file write
    is not force-gated, so on a workspace vaultspec has never claimed locally
    these are the only files adoption can silently destroy - live edits in a
    checkout whose projections were tracked in version control.

    The comparison is delegated to :func:`collect_content_integrity`, the same
    comparator the doctor and the sync engine share, so adoption cannot grow a
    second, divergent notion of what "diverged" means. It reads the manifest
    nowhere, which is what makes it computable on an unmanifested workspace.

    Args:
        target: Workspace root directory.

    Returns:
        Sorted workspace-relative paths (forward-slash separated) of diverged
        projections; empty when every projection matches its source or when
        tool configuration cannot be resolved.
    """
    from ..enums import Tool
    from ..types import WorkspaceContext, get_context, set_context

    # Resolving tool configs needs the workspace context, which this collector
    # must not leave mutated: the diagnosis layer is specified as side-effect
    # free. Snapshot whatever was active and restore it unconditionally.
    previous: WorkspaceContext | None
    try:
        previous = get_context()
    except LookupError:
        previous = None

    try:
        try:
            from ..commands import _ensure_tool_configs

            _ensure_tool_configs(target)
            ctx = get_context()
        except Exception:
            logger.debug(
                "Could not bootstrap tool configs for adoption probe", exc_info=True
            )
            return []

        diverged: set[str] = set()
        for tool in Tool:
            dir_name = _TOOL_DIR.get(tool.value)
            if dir_name is None or not (target / dir_name).is_dir():
                continue
            cfg = ctx.tool_configs.get(tool)
            if cfg is None or cfg.rules_dir is None:
                continue
            try:
                content = collect_content_integrity(tool.value)
            except Exception:
                logger.debug(
                    "Content integrity probe failed for %s", tool.value, exc_info=True
                )
                continue
            for name, signal in content.items():
                if signal is not ContentSignal.DIVERGED:
                    continue
                dest = cfg.rules_dir / name
                try:
                    rel = dest.relative_to(target)
                except ValueError:
                    rel = dest
                diverged.add(str(rel).replace("\\", "/"))

        return sorted(diverged)
    finally:
        if previous is not None:
            set_context(previous)


def collect_rename_integrity(target: Path) -> tuple[RenameIntegritySignal, int]:
    """Check name/filename integrity for rules, skills, and agents.

    Args:
        target: Workspace root directory.

    Returns:
        ``(signal, mismatch_count)``.
    """
    from ...vaultcore.checks import Severity
    from ...vaultcore.checks.rename_integrity import check_rename_integrity

    try:
        result = check_rename_integrity(target)
        mismatch_count = 0
        has_error = False

        for diag in result.diagnostics:
            if diag.severity == Severity.ERROR:
                if "does not match expected name" in diag.message:
                    mismatch_count += 1
                else:
                    has_error = True

        if has_error:
            return RenameIntegritySignal.ERROR, mismatch_count
        if mismatch_count > 0:
            return RenameIntegritySignal.MISMATCH, mismatch_count
        return RenameIntegritySignal.CLEAN, 0
    except Exception as exc:
        logger.warning("Rename integrity collector failed: %s", exc, exc_info=True)
        return RenameIntegritySignal.ERROR, 0
