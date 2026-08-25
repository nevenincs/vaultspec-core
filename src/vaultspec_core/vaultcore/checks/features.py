"""Check feature tag completeness  - detect features missing required doc types."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    extract_feature_tags,
    is_generated_index,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["check_features"]


def _count_index_related(snapshot: VaultSnapshot) -> dict[str, int]:
    """Return a mapping of feature name to ``related:`` count for indexes.

    Only considers files matching the ``*.index.md`` naming convention.
    """
    counts: dict[str, int] = {}
    for doc_path, (metadata, _body) in snapshot.items():
        if not is_generated_index(doc_path):
            continue
        # Feature name is the stem minus ".index" suffix
        stem = doc_path.stem  # e.g. "my-feature.index"
        feat = stem.removesuffix(".index")
        counts[feat] = len(metadata.related)
    return counts


def _link_stems(related: list[str]) -> set[str]:
    """Return the document stems a ``related:`` field points at.

    Entries are Obsidian wiki-links (``[[stem]]``); anything else is left
    alone so a malformed entry simply matches nothing.
    """
    stems: set[str] = set()
    for entry in related:
        text = entry.strip()
        if text.startswith("[[") and text.endswith("]]"):
            text = text[2:-2]
        target = text.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            stems.add(target)
    return stems


def check_features(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
) -> CheckResult:
    """Check that features have appropriate document type coverage.

    Rules enforced:

    - exec only, no plan or ADR: WARNING
    - plan present, no ADR: WARNING
    - ADR present, no research: INFO (soft recommendation)
    - feature has documents but no ``<feature>.index.md``: WARNING
    - feature index exists but ``related:`` count differs from actual
      document count: WARNING (stale index)

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed data.
        feature: Restrict checks to a single feature (without ``#``).

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"features"``. Does not support ``--fix``.
    """
    from ..scanner import get_doc_type

    result = CheckResult(check_name="features", supports_fix=False)

    # One pass over the snapshot collects everything the per-feature loop
    # needs: the doc-type sets, the per-feature document counts, and the
    # index-file name set. No helper below re-scans the snapshot, so the
    # check stays linear in corpus size instead of features x documents.
    by_feature: dict[str, set[str]] = {}
    doc_counts: dict[str, int] = {}
    index_names: set[str] = set()
    stem_types: dict[str, str] = {}
    plan_grounding: dict[str, set[str]] = {}
    for doc_path, (metadata, _body) in snapshot.items():
        if is_generated_index(doc_path):
            index_names.add(doc_path.name)
            continue
        feat_tags = extract_feature_tags(metadata.tags)
        dt = get_doc_type(doc_path, root_dir)
        dt_value = dt.value if dt else None
        if dt_value:
            stem_types[doc_path.stem] = dt_value
        for ft in set(feat_tags):
            doc_counts[ft] = doc_counts.get(ft, 0) + 1
            if dt_value:
                by_feature.setdefault(ft, set()).add(dt_value)
            if dt_value == "plan":
                plan_grounding.setdefault(ft, set()).update(
                    _link_stems(metadata.related)
                )

    if feature:
        feat = feature.lstrip("#")
        by_feature = {k: v for k, v in by_feature.items() if k == feat}

    index_related_counts = _count_index_related(snapshot)

    for feat_name, types in sorted(by_feature.items()):
        if feat_name == "uncategorized":
            continue

        # A plan may execute an ADR that belongs to another feature - the
        # sanctioned cluster and roll-up shape, where every governing ADR is
        # named in the plan's ``related:``. Judging backing by feature-tag
        # co-membership alone reports those correctly grounded plans as
        # unbacked.
        has_adr = "adr" in types or any(
            stem_types.get(stem) == "adr" for stem in plan_grounding.get(feat_name, ())
        )
        has_plan = "plan" in types
        has_research = "research" in types
        has_exec = "exec" in types
        if has_exec and not has_plan and not has_adr:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=None,
                    message=(
                        f"Feature '{feat_name}' has execution records "
                        f"but no plan or ADR. "
                        f"Types present: {', '.join(sorted(types))}"
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        "Consider: "
                        f"vaultspec-core vault add plan -f {feat_name} && "
                        f"vaultspec-core vault add adr -f {feat_name}"
                    ),
                )
            )

        if has_plan and not has_adr:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=None,
                    message=(
                        f"Feature '{feat_name}' has a plan but no ADR. "
                        f"Plans should be backed by an "
                        f"architectural decision."
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        f"Consider: vaultspec-core vault add adr -f {feat_name}"
                    ),
                )
            )

        if has_adr and not has_research:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=None,
                    message=(
                        f"Feature '{feat_name}' has an ADR but no "
                        f"research document. Research docs help "
                        f"justify architectural decisions."
                    ),
                    severity=Severity.INFO,
                    fix_description=(
                        f"Consider: vaultspec-core vault add research -f {feat_name}"
                    ),
                )
            )

        # -- Index health checks --

        # Filename-based and folder-agnostic: both legacy root-level indexes
        # and the canonical index/ subfolder layout satisfy the predicate.
        if f"{feat_name}.index.md" not in index_names:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=None,
                    message=(
                        f"Feature '{feat_name}' has no feature index. Run "
                        "vaultspec-core vault feature index to generate "
                        f"index/{feat_name}.index.md"
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        f"vaultspec-core vault feature index -f {feat_name}"
                    ),
                )
            )
        else:
            # Index exists - check staleness
            actual_count = doc_counts.get(feat_name, 0)
            index_count = index_related_counts.get(feat_name, 0)
            if index_count != actual_count:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=None,
                        message=(
                            f"Feature '{feat_name}' index is stale: "
                            f"related: has {index_count} links but "
                            f"feature has {actual_count} documents. "
                            "Run vaultspec-core vault feature index to rebuild"
                        ),
                        severity=Severity.WARNING,
                        fix_description=(
                            f"vaultspec-core vault feature index -f {feat_name}"
                        ),
                    )
                )

    return result
