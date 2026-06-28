"""Vault health check suite for ``.vault/`` content.

Re-exports the result contract
(:class:`~vaultspec_core.vaultcore.checks._base.CheckResult`,
:class:`~vaultspec_core.vaultcore.checks._base.CheckDiagnostic`,
:class:`~vaultspec_core.vaultcore.checks._base.Severity`) and all
checker functions from their submodules. Use :func:`run_all_checks` for a
combined pass or call individual checkers. Consumed by
:mod:`vaultspec_core.cli` and :mod:`vaultspec_core.mcp_server`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultDocData,
    VaultSnapshot,
    render_check_result,
)
from .adr_status import check_adr_status
from .annotations import check_annotations
from .body_links import check_body_links
from .dangling import check_dangling
from .encoding import check_encoding
from .feature_rename_integrity import check_feature_rename_integrity
from .features import check_features
from .frontmatter import check_frontmatter
from .links import check_links
from .markdown import check_markdown
from .modified_stamp import check_modified_stamp
from .orphans import check_orphans
from .placeholders import check_placeholders
from .references import check_references, check_schema
from .rename_integrity import check_rename_integrity
from .structure import check_structure

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CheckDiagnostic",
    "CheckResult",
    "Severity",
    "VaultDocData",
    "VaultSnapshot",
    "check_adr_status",
    "check_annotations",
    "check_body_links",
    "check_dangling",
    "check_encoding",
    "check_feature_rename_integrity",
    "check_features",
    "check_frontmatter",
    "check_links",
    "check_markdown",
    "check_modified_stamp",
    "check_orphans",
    "check_placeholders",
    "check_references",
    "check_rename_integrity",
    "check_schema",
    "check_structure",
    "render_check_result",
    "run_all_checks",
]


def run_all_checks(
    root_dir: Path,
    *,
    feature: str | None = None,
    fix: bool = False,
) -> list[CheckResult]:
    """Run all vault health checkers and return their results.

    Executes structure, frontmatter, modified-stamp, annotations, markdown,
    links, dangling, body-links, placeholders, orphans, features,
    feature-rename-integrity, references, schema, adr-status,
    rename-integrity, and encoding checks in order. Builds a single
    :class:`~vaultspec_core.graph.VaultGraph` and shares it across
    graph-consuming checkers to avoid redundant I/O.

    Args:
        root_dir: Project root directory.
        feature: Restrict per-document checks to this feature tag (without ``#``).
        fix: When ``True``, pass ``fix=True`` to all supporting checkers.

    Returns:
        List of :class:`~vaultspec_core.vaultcore.checks._base.CheckResult`,
        one per checker, in the order above.
    """
    from ...graph import VaultGraph

    if not fix:
        graph = VaultGraph(root_dir)
        snapshot = graph.to_snapshot()
        return [
            check_structure(root_dir, snapshot=snapshot, fix=False),
            check_frontmatter(root_dir, snapshot=snapshot, feature=feature, fix=False),
            check_modified_stamp(
                root_dir, snapshot=snapshot, feature=feature, fix=False
            ),
            check_annotations(root_dir, feature=feature, fix=False),
            check_markdown(root_dir, feature=feature, fix=False),
            check_links(root_dir, snapshot=snapshot, feature=feature, fix=False),
            check_dangling(root_dir, graph=graph, feature=feature, fix=False),
            check_body_links(root_dir, snapshot=snapshot, feature=feature),
            check_placeholders(root_dir, snapshot=snapshot, feature=feature),
            check_orphans(root_dir, graph=graph, feature=feature),
            check_features(root_dir, snapshot=snapshot, feature=feature),
            check_feature_rename_integrity(root_dir),
            check_references(root_dir, graph=graph, feature=feature, fix=False),
            check_schema(root_dir, graph=graph, feature=feature, fix=False),
            check_adr_status(root_dir, snapshot=snapshot, feature=feature, fix=False),
            check_rename_integrity(root_dir, fix=False),
            check_encoding(root_dir),
        ]

    # Mutating checks can rename files or rewrite frontmatter. Refresh graph
    # state only after a checker reports a mutation.
    results: list[CheckResult] = []
    graph = VaultGraph(root_dir)

    def append_and_refresh(result: CheckResult) -> None:
        nonlocal graph
        results.append(result)
        if result.fixed_count:
            graph = VaultGraph(root_dir)

    result = check_structure(root_dir, snapshot=graph.to_snapshot(), fix=True)
    append_and_refresh(result)

    result = check_frontmatter(
        root_dir,
        snapshot=graph.to_snapshot(),
        feature=feature,
        fix=True,
    )
    append_and_refresh(result)

    # The modified-stamp fix only inserts or rewrites a single frontmatter
    # line; it never renames files or changes links, so it cannot invalidate
    # the graph for the downstream checkers. Appending without a graph
    # rebuild keeps the structure-rename cascade (which the repair pipeline
    # depends on) intact - a mid-cascade rebuild here re-resolves a
    # case-only rename against a stale snapshot on case-insensitive
    # filesystems and strands the original-cased file.
    result = check_modified_stamp(
        root_dir,
        snapshot=graph.to_snapshot(),
        feature=feature,
        fix=True,
    )
    results.append(result)

    result = check_annotations(root_dir, feature=feature, fix=True)
    append_and_refresh(result)

    # Markdown hygiene rewrites only line whitespace and blank runs - it never
    # touches frontmatter, links, or filenames, so it cannot invalidate the
    # graph. Run it after annotations so blank lines left by stripped comment
    # blocks are collapsed in the same pass.
    results.append(check_markdown(root_dir, feature=feature, fix=True))

    result = check_links(
        root_dir, snapshot=graph.to_snapshot(), feature=feature, fix=True
    )
    append_and_refresh(result)

    result = check_dangling(root_dir, graph=graph, feature=feature, fix=True)
    append_and_refresh(result)

    results.append(
        check_body_links(root_dir, snapshot=graph.to_snapshot(), feature=feature)
    )
    results.append(
        check_placeholders(root_dir, snapshot=graph.to_snapshot(), feature=feature)
    )
    results.append(check_orphans(root_dir, graph=graph, feature=feature))
    results.append(
        check_features(root_dir, snapshot=graph.to_snapshot(), feature=feature)
    )
    # Feature-rename-integrity is read-only (reconciling drift is a feature
    # rename, not a frontmatter rewrite); it runs identically in both modes.
    results.append(check_feature_rename_integrity(root_dir))

    result = check_references(root_dir, graph=graph, feature=feature, fix=True)
    append_and_refresh(result)

    results.append(check_schema(root_dir, graph=graph, feature=feature, fix=True))

    # adr-status fix only rewrites the H1 status token's backtick quoting; it
    # never touches frontmatter, links, or filenames, so it cannot invalidate
    # the graph. Refresh anyway when it mutates, to keep the snapshot honest.
    result = check_adr_status(
        root_dir, snapshot=graph.to_snapshot(), feature=feature, fix=True
    )
    append_and_refresh(result)

    results.append(check_rename_integrity(root_dir, fix=True))
    # Encoding is read-only (non-UTF-8 cannot be auto-rewritten without silently
    # mutating bytes); it runs identically in both modes.
    results.append(check_encoding(root_dir))
    return results
