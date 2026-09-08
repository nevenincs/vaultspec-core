"""Check missing cross-references and enforce schema rules.

Two checks in one module:
- references: feature docs that should reference each other but don't
- schema: ADRs must reference grounding (research/reference/audit);
  active plans must reference accepted decisions when decisions govern

Missing semantic links are reported; repair does not choose evidence or authority.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

    from ...graph import DocNode, VaultGraph

__all__ = ["check_references", "check_schema"]


def check_references(
    root_dir: Path,
    *,
    graph: VaultGraph,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Check for missing cross-references within features.

    For each feature, finds research documents not referenced by any plan
    or ADR in the same feature.

    Args:
        root_dir: Project root directory.
        graph: Pre-built vault graph to query (avoids redundant I/O).
        feature: Restrict checks to a single feature (without ``#``).
        fix: Accepted for compatibility; semantic evidence is never auto-selected.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"references"``.
    """
    from ..models import DocType

    del fix  # Semantic relationships require an explicit author selection.
    result = CheckResult(check_name="references", supports_fix=False)

    # Group nodes by feature (skip phantoms - they have no real doc type)
    by_feature: dict[str, dict[str, list[DocNode]]] = {}
    for _name, node in graph.nodes.items():
        if node.phantom:
            continue
        for tag in node.tags:
            if not DocType.from_tag(tag):
                feat = tag.lstrip("#")
                by_feature.setdefault(feat, {}).setdefault(
                    node.doc_type.value if node.doc_type else "unknown", []
                ).append(node)

    if feature:
        feat = feature.lstrip("#")
        by_feature = {k: v for k, v in by_feature.items() if k == feat}

    for feat_name, types_map in sorted(by_feature.items()):
        if feat_name == "uncategorized":
            continue

        research_docs = types_map.get("research", [])
        plan_docs = types_map.get("plan", [])
        adr_docs = types_map.get("adr", [])

        if not research_docs:
            continue

        # Collect all outgoing links from plans and ADRs in this feature
        plan_adr_links: set[str] = set()
        for doc in plan_docs + adr_docs:
            plan_adr_links.update(doc.out_links)

        # Check if research docs are referenced
        for research_node in research_docs:
            if research_node.name not in plan_adr_links and not research_node.in_links:
                referencing_types: list[str] = []
                if adr_docs:
                    referencing_types.append("ADR")

                if not referencing_types:
                    continue

                result.diagnostics.append(
                    CheckDiagnostic(
                        path=(
                            research_node.path.relative_to(root_dir)
                            if research_node.path is not None
                            else None
                        ),
                        message=(
                            f"Research doc not referenced by any "
                            f"{'/'.join(referencing_types)} in feature "
                            f"'{feat_name}'"
                        ),
                        severity=Severity.WARNING,
                        fixable=False,
                        fix_description=(
                            f"Add [[{research_node.name}]] to related field "
                            f"in a {'/'.join(referencing_types)} document"
                        ),
                    )
                )

    return result


def _is_filtered_out(
    node: DocNode, feature: str | None, doc_type_filter: str | None
) -> bool:
    """Return True when *node* falls outside the requested type/feature filter.

    An untyped node cannot satisfy a type filter, so it is filtered out. The
    caller already skips those, but stating it here keeps the helper correct
    on its own terms rather than relying on narrowing it cannot see.
    """
    if doc_type_filter and (
        node.doc_type is None or node.doc_type.value != doc_type_filter
    ):
        return True
    if not feature:
        return False
    # Feature filter (normalize: always compare stripped values)
    feat = feature.lstrip("#")
    return feat not in {t.lstrip("#") for t in node.tags}


def _linked_doc_types(graph: VaultGraph, node: DocNode) -> set[str]:
    """Classify outgoing link targets by doc type (skip phantoms)."""
    linked_types: set[str] = set()
    for target_name in node.out_links:
        target = graph.nodes.get(target_name)
        if target and not target.phantom and target.doc_type:
            linked_types.add(target.doc_type.value)
    return linked_types


def _primary_feature_name(node: DocNode) -> str | None:
    """Return the node's first feature tag without its ``#``, if any."""
    from ..models import DocType

    feat_tags = [t for t in node.tags if not DocType.from_tag(t)]
    return feat_tags[0].lstrip("#") if feat_tags else None


def _check_adr_grounding(
    rel_path: Path,
    feat_name: str | None,
    linked_types: set[str],
    result: CheckResult,
) -> None:
    """Require an ADR to reference research, reference, or audit grounding."""
    # The documentation hierarchy sanctions research, reference, and audit
    # documents as ADR grounding; any one of them satisfies the check.
    grounding_types = ("research", "reference", "audit")
    if linked_types & set(grounding_types):
        return

    msg = "ADR has no grounding references (research, reference, or audit documents)"
    if feat_name:
        msg += f" (feature: {feat_name})"
    result.diagnostics.append(
        CheckDiagnostic(
            path=rel_path,
            message=msg,
            severity=Severity.ERROR,
            fixable=False,
            fix_description=(
                "Select sufficient research, reference, or audit evidence "
                "and link it explicitly in related"
            ),
        )
    )


def _check_plan_grounding(
    node: DocNode,
    graph: VaultGraph,
    rel_path: Path,
    result: CheckResult,
) -> None:
    """Check explicit authority for active plans without inventing missing decisions."""
    import yaml

    from ...core.adr import adr_status_from_body
    from ...core.enums import AdrStatus
    from ...plan.parser import mask_html_comments_text, parse_plan
    from ..models import DocType

    body = mask_html_comments_text(node.body)
    approved = re.search(
        r"^## Description\s*\n(?:[ \t]*\n)*[ \t]*Approved \d{4}-\d{2}-\d{2}\s*$",
        body,
        re.MULTILINE,
    )
    if not approved:
        return
    try:
        source = "---\n" + yaml.safe_dump(node.frontmatter) + "---\n" + body
        steps = parse_plan(source).steps
    except ValueError as exc:
        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=f"Cannot assess plan authority: {exc}",
                severity=Severity.ERROR,
            )
        )
        return
    if steps and all(step.checked for step in steps):
        return
    for name in sorted(node.out_links):
        target = graph.nodes.get(name)
        if target is None or target.phantom or target.doc_type != DocType.ADR:
            continue
        if adr_status_from_body(
            target.body
        ) != AdrStatus.ACCEPTED or target.frontmatter.get("superseded_by"):
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"Active approved plan references non-accepted ADR '{name}'; "
                        "reassess decision coverage before execution"
                    ),
                    severity=Severity.ERROR,
                )
            )


def check_schema(
    root_dir: Path,
    *,
    graph: VaultGraph,
    feature: str | None = None,
    doc_type_filter: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Enforce schema-level cross-reference rules on ADRs and plans.

    Rules enforced:

    - ADR must reference at least one grounding document - research,
      reference, or audit (ERROR).
    - Active approved plans require their linked governing ADRs to be accepted.
    - Decision-free plans are valid; evidence is inherited through ADR links.

    Missing semantic links are never inferred from feature co-membership.

    Args:
        root_dir: Project root directory.
        graph: Pre-built vault graph to query (avoids redundant I/O).
        feature: Restrict checks to documents with this feature tag
            (without ``#``).
        doc_type_filter: Restrict checks to this document type
            (e.g. ``"adr"``).
        fix: Accepted for compatibility; semantic evidence is never auto-selected.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"schema"``.
    """
    from ..models import DocType

    del fix  # Retain the public call signature without manufacturing evidence.
    result = CheckResult(check_name="schema", supports_fix=False)

    for _name, node in sorted(graph.nodes.items()):
        if not node.doc_type or node.path is None:
            continue

        if _is_filtered_out(node, feature, doc_type_filter):
            continue

        linked_types = _linked_doc_types(graph, node)
        rel_path = node.path.relative_to(root_dir)
        feat_name = _primary_feature_name(node)

        if node.doc_type == DocType.ADR:
            _check_adr_grounding(
                rel_path,
                feat_name,
                linked_types,
                result,
            )
        elif node.doc_type == DocType.PLAN:
            _check_plan_grounding(node, graph, rel_path, result)

    return result
