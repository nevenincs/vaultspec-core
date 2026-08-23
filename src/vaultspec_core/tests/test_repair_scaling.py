"""Guards that the repair pipeline stays linear in document count.

The dry-run index preview once built a fresh, cache-disabled vault graph - a
full parse of every document - once per feature, giving a cost proportional to
features multiplied by documents. On a 1,229-document vault with 130 features
that was 159,770 document parses; at 10,476 documents the command produced no
output in twenty minutes.

The defect is invisible to a correctness test: the preview returned the right
answer, just eventually. It is also invisible on a small fixture, where a
handful of rebuilds of a tiny vault finish quickly. So it is guarded by
counting the work rather than by timing it - a wall-clock threshold would be
flaky on a loaded machine and would say nothing about *why* it regressed.

The count comes from the graph builder's own log line rather than from
substituting the builder, so the guard observes the real pipeline.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: Emitted once per full graph construction by ``VaultGraph._build_graph``.
_BUILD_MARKER = "Building vault graph from"


def _write_doc(root: Path, feature: str, index: int) -> None:
    """Write one minimal research document for *feature*.

    Args:
        root: The workspace root.
        feature: The feature tag to carry.
        index: Distinguishes the filename and date.
    """
    path = root / ".vault" / "research" / f"2026-01-{index:02d}-{feature}-research.md"
    path.write_text(
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        f"  - '#{feature}'\n"
        f"date: '2026-01-{index:02d}'\n"
        f"modified: '2026-01-{index:02d}'\n"
        "related: []\n"
        "---\n\n"
        f"# {feature} research\n\nBody.\n",
        encoding="utf-8",
    )


def test_repair_does_not_rebuild_the_graph_once_per_feature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Graph builds must not grow with the number of features.

    The regression guard for the index preview's per-feature rebuild. A handful
    of builds is expected - the pipeline legitimately builds one for the
    preview and one or two more for the check and postcheck passes - but the
    count must not track the feature count.
    """
    from vaultspec_core.vaultcore.repair import run_repair_pipeline

    root = tmp_path / "scaling"
    root.mkdir()
    WorkspaceFactory(root).install()

    features = 12
    for n in range(features):
        _write_doc(root, f"scaling-feat-{n}", n + 1)

    with caplog.at_level(logging.INFO, logger="vaultspec_core.graph.api"):
        run_repair_pipeline(root, dry_run=True)

    builds = sum(1 for record in caplog.records if _BUILD_MARKER in record.getMessage())

    assert builds <= features, (
        f"repair built the vault graph {builds} times over {features} features. "
        "A count that tracks the feature count means a per-feature rebuild has "
        "returned, which is O(features x documents): it cost 20 minutes at "
        "10,476 documents and produced no output."
    )


def test_the_feature_index_generator_uses_the_graph_cache() -> None:
    """Index generation must not disable the cache.

    Disabling it forced a full parse of every document on every call, and the
    repair pipeline calls this once per feature. The cache validates by file
    set, size, mtime and content hash and rebuilds on any divergence, so it
    cannot serve a stale membership - disabling it bought nothing.
    """
    import inspect

    from vaultspec_core.vaultcore import index

    source = inspect.getsource(index.generate_feature_index_result)

    assert "use_cache=False" not in source, (
        "feature index generation disabled the graph cache, forcing a full "
        "vault parse per call"
    )
