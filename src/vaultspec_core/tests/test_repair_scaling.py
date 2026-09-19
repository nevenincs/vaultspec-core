"""Guards that feature-index generation stays linear in document count.

Every batch that regenerates feature indexes - the ``vault feature index``
verb, the repair pipeline's index preview and its mutating index phase, and
the MCP write tools' post-batch refresh - must read the vault corpus once and
slice it per feature. Calling the single-feature generator in a loop instead
makes each iteration build its own whole-vault graph, which is
``O(features x documents)``.

The cost is not theoretical. On a 745-feature, 4,739-document vault the verb
took 18m39s to decide that no index needed writing, and 461s to rewrite 60
indexes that the shared-graph path rewrites byte-for-byte identically in 12s.

The defect is invisible to a correctness test: every path returned the right
answer, just eventually. It is also invisible on a small fixture, where a
handful of rebuilds of a tiny vault finish quickly. So it is guarded by
counting the work rather than by timing it - a wall-clock threshold would be
flaky on a loaded machine and would say nothing about *why* it regressed.

The count comes from the graph builder's own log line rather than from
substituting the builder, so the guard observes the real pipeline. The
threshold is a small constant rather than a multiple of the feature count: an
earlier guard allowed ``builds <= features``, which is roughly what the
per-feature rebuild it was meant to catch actually produces.
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

#: Features created by :func:`_vault_with_features`. Larger than any
#: legitimate build count so that "builds track features" is distinguishable
#: from "builds are a small constant".
_FEATURES = 12

#: The most graph builds any single index batch may perform. A batch needs one
#: build to enumerate features and slice membership; the repair pipeline
#: legitimately adds builds for its check and postcheck passes. None of them
#: may scale with the feature count.
_BUILD_CEILING = 6


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


def _vault_with_features(tmp_path: Path, name: str) -> tuple[Path, list[str]]:
    """Build an installed workspace carrying :data:`_FEATURES` features.

    Args:
        tmp_path: The pytest temporary directory.
        name: Subdirectory name, so several vaults can coexist in one test.

    Returns:
        The workspace root and the feature names it carries.
    """
    root = tmp_path / name
    root.mkdir()
    WorkspaceFactory(root).install()
    features = [f"scaling-feat-{n}" for n in range(_FEATURES)]
    for n, feature in enumerate(features):
        _write_doc(root, feature, n + 1)
    return root, features


def _count_builds(caplog: pytest.LogCaptureFixture) -> int:
    """Return how many full graph builds the captured log recorded."""
    return sum(1 for record in caplog.records if _BUILD_MARKER in record.getMessage())


def _assert_linear(builds: int, what: str) -> None:
    """Fail when *builds* tracks the feature count rather than a constant.

    Args:
        builds: Observed full graph constructions.
        what: The batch path under test, for the failure message.
    """
    assert builds <= _BUILD_CEILING, (
        f"{what} built the vault graph {builds} times over {_FEATURES} features, "
        f"above the ceiling of {_BUILD_CEILING}. A count that tracks the feature "
        "count means a per-feature rebuild has returned, which is "
        "O(features x documents): it cost 18m39s over 745 features at 4,739 "
        "documents and wrote nothing."
    )


def test_repair_preview_does_not_rebuild_the_graph_once_per_feature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The repair index preview must slice one graph."""
    from vaultspec_core.vaultcore.repair import run_repair_pipeline

    root, _ = _vault_with_features(tmp_path, "preview")

    with caplog.at_level(logging.INFO, logger="vaultspec_core.graph.api"):
        run_repair_pipeline(root, dry_run=True)

    _assert_linear(_count_builds(caplog), "the repair index preview")


def test_repair_apply_does_not_rebuild_the_graph_once_per_feature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The repair index phase must slice one graph when it actually writes.

    The preview was fixed first and the mutating phase deliberately left on the
    per-feature rebuild, so a guard on the preview alone did not cover the path
    that does the work.
    """
    from vaultspec_core.vaultcore.repair import _refresh_indexes

    root, _ = _vault_with_features(tmp_path, "apply")

    with caplog.at_level(logging.INFO, logger="vaultspec_core.graph.api"):
        generated = _refresh_indexes(root, None)

    assert len(generated) == _FEATURES, (
        "the index phase must still write one index per feature; "
        f"it wrote {len(generated)}"
    )
    _assert_linear(_count_builds(caplog), "the repair index phase")


def test_feature_index_verb_does_not_rebuild_the_graph_once_per_feature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``vault feature index`` must slice the graph it already built.

    The verb built a graph to enumerate features, discarded it, and then built
    another one per feature inside the generator.
    """
    import typer

    from vaultspec_core.cli.vault_feature_cmd import _run_feature_index

    root, features = _vault_with_features(tmp_path, "verb")

    with (
        caplog.at_level(logging.INFO, logger="vaultspec_core.graph.api"),
        pytest.raises(typer.Exit),
    ):
        _run_feature_index(None, json_output=True, target=root)

    index_dir = root / ".vault" / "index"
    written = sorted(p.name for p in index_dir.glob("*.index.md"))
    assert written == sorted(f"{f}.index.md" for f in features), (
        "the verb must still write one index per feature"
    )
    _assert_linear(_count_builds(caplog), "the vault feature index verb")


def test_mcp_batch_refresh_does_not_rebuild_the_graph_once_per_feature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The MCP post-batch index refresh must slice one graph.

    Each index this refresh writes is itself a scanned document, so a loop also
    invalidated the fingerprint cache it had just refreshed - every iteration
    after the first paid a cold rebuild.
    """
    from vaultspec_core.mcp_server.tools.documents import _regenerate_indexes

    root, features = _vault_with_features(tmp_path, "mcp")

    with caplog.at_level(logging.INFO, logger="vaultspec_core.graph.api"):
        _regenerate_indexes(root, set(features))

    index_dir = root / ".vault" / "index"
    written = sorted(p.name for p in index_dir.glob("*.index.md"))
    assert written == sorted(f"{f}.index.md" for f in features), (
        "the refresh must still write one index per touched feature"
    )
    _assert_linear(_count_builds(caplog), "the MCP post-batch index refresh")


def test_shared_graph_slicing_matches_a_per_feature_read(tmp_path: Path) -> None:
    """The fast path must produce exactly what the per-feature read produced.

    Slicing one snapshot changes membership only under concurrent external
    mutation, which the per-feature index lock never guarded against anyway:
    the lock covers one index file, while membership is decided by ``#feature``
    tags in ordinary documents that never take that sentinel. Within one batch
    the two are provably identical, because an index document is excluded from
    its own feature's rendered membership - so no write the batch performs can
    change what a later feature in the same batch would read.
    """
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.index import (
        generate_feature_index_result,
        generate_feature_indexes,
    )

    per_feature_root, features = _vault_with_features(tmp_path, "per-feature")
    shared_root, _ = _vault_with_features(tmp_path, "shared")

    for feature in features:
        generate_feature_index_result(per_feature_root, feature, date_str="2026-03-23")
    generate_feature_indexes(
        shared_root,
        features,
        graph=VaultGraph(shared_root),
        date_str="2026-03-23",
    )

    for feature in features:
        name = f"{feature}.index.md"
        assert (shared_root / ".vault" / "index" / name).read_bytes() == (
            per_feature_root / ".vault" / "index" / name
        ).read_bytes(), f"shared-graph slicing changed the index body for {feature}"


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
