"""Scale benchmarks for the vault graph build and fingerprint cache.

These are regression tripwires, not tight SLAs: the thresholds are
deliberately generous so the suite catches an order-of-magnitude regression
(an accidental O(n^2) parse, a lost cache, a doubled metrics pass) without
flaking on a slow CI box.  They build real synthetic corpora at 500 and 5000
documents - the scale envelope the ADR targets - and assert the cold build
completes and that a warm cache load is no slower than the cold build.

Marked :data:`pytest.mark.benchmark` so the default ``pytest`` run (which
deselects ``benchmark`` via the ``addopts`` marker expression) skips them;
run them explicitly with ``pytest -m benchmark``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from .. import cache as cache_mod
from ..api import VaultGraph

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.benchmark]

# Generous ceilings: a healthy build at this scale is well under these.  The
# point is to fail loudly on a structural regression, not to police seconds.
_COLD_BUILD_CEILING_SECONDS = {500: 30.0, 5000: 240.0}


def _build_corpus(root: Path, n_docs: int) -> None:
    """Generate a connected synthetic corpus of *n_docs* documents."""
    reset_config()
    build_synthetic_vault(root, n_docs=n_docs, seed=9, edge_probability=0.3)


@pytest.mark.parametrize("n_docs", [500, 5000])
def test_cold_build_completes(tmp_path: Path, n_docs: int) -> None:
    """A from-scratch build of *n_docs* documents completes within budget."""
    _build_corpus(tmp_path, n_docs)

    start = time.perf_counter()
    graph = VaultGraph(tmp_path, use_cache=False)
    elapsed = time.perf_counter() - start

    # The synthetic generator distributes n_docs across six type dirs, so the
    # real-node count is at least n_docs (phantoms may add a few more).
    real_nodes = sum(1 for node in graph.nodes.values() if not node.phantom)
    assert real_nodes >= n_docs
    assert elapsed < _COLD_BUILD_CEILING_SECONDS[n_docs], (
        f"cold build of {n_docs} docs took {elapsed:.2f}s "
        f"(ceiling {_COLD_BUILD_CEILING_SECONDS[n_docs]}s)"
    )


@pytest.mark.parametrize("n_docs", [500, 5000])
def test_warm_cache_no_slower_than_cold(tmp_path: Path, n_docs: int) -> None:
    """A warm cache load is no slower than the cold parse it replaces."""
    _build_corpus(tmp_path, n_docs)

    start = time.perf_counter()
    cold = VaultGraph(tmp_path, use_cache=False)
    cold_elapsed = time.perf_counter() - start

    # Prime the cache with one cached build, then time a guaranteed hit.
    VaultGraph(tmp_path)
    assert cache_mod.cache_path(tmp_path).exists()

    start = time.perf_counter()
    warm = VaultGraph(tmp_path)
    warm_elapsed = time.perf_counter() - start

    # Identical topology, and the warm load is not slower than the cold parse.
    assert warm.digraph.number_of_nodes() == cold.digraph.number_of_nodes()
    assert warm.digraph.number_of_edges() == cold.digraph.number_of_edges()
    assert warm_elapsed <= cold_elapsed, (
        f"warm cache load of {n_docs} docs took {warm_elapsed:.2f}s, "
        f"slower than the cold build's {cold_elapsed:.2f}s"
    )
