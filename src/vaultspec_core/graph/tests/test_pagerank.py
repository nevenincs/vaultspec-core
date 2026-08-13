"""Exact-value behavioural tests for the pure-Python PageRank helper.

The project ships neither NumPy nor SciPy, so :func:`networkx.pagerank` cannot
run here; :func:`vaultspec_core.graph.algorithms.pagerank` is the deterministic
pure-Python power-iteration substitute used for node sizing.  These tests
exercise that real function over real :class:`networkx.DiGraph` structures - no
mocks, no patched networkx - and assert analytic values.

Where a result is exact by symmetry (a balanced cycle yields a uniform vector;
every stochastic vector sums to ``1.0``) the assertion is exact.  Where a value
is only convergent-exact (the relative ranking of a hub against its leaves after
power iteration) the assertion is a strict inequality, which the converged
iterate satisfies with margin far larger than the ``n * tol`` convergence
threshold.
"""

from __future__ import annotations

import pytest

from ...graph.algorithms import pagerank
from ...graph.networkx_runtime import NetworkXGraph, directed_graph

pytestmark = [pytest.mark.unit]


def test_empty_graph_yields_empty_mapping() -> None:
    """An empty graph has no nodes to rank."""
    assert pagerank(directed_graph()) == {}


class TestSymmetricCycle:
    """A balanced directed cycle ranks every node identically."""

    def _cycle(self) -> NetworkXGraph:
        g = directed_graph()
        # 0 -> 1 -> 2 -> 0: every node has exactly one in- and one out-edge.
        g.add_edges_from([("0", "1"), ("1", "2"), ("2", "0")])
        return g

    def test_each_node_is_one_third(self):
        scores = pagerank(self._cycle())
        # By symmetry the stationary distribution is uniform: 1/3 each.  The
        # cycle has no dangling nodes and the teleport term is uniform, so the
        # uniform vector is an exact fixed point reached on the first iterate.
        for node in ("0", "1", "2"):
            assert scores[node] == pytest.approx(1.0 / 3.0, abs=1e-12)

    def test_vector_sums_to_one(self):
        scores = pagerank(self._cycle())
        assert sum(scores.values()) == pytest.approx(1.0, abs=1e-12)


class TestStarHubRanksAboveLeaves:
    """A star whose leaves all point at the hub ranks the hub strictly highest."""

    def _star(self) -> NetworkXGraph:
        g = directed_graph()
        # Three leaves each link to a single shared hub; the hub links back to
        # one leaf so the hub is not itself dangling.
        g.add_edges_from(
            [
                ("leaf-a", "hub"),
                ("leaf-b", "hub"),
                ("leaf-c", "hub"),
                ("hub", "leaf-a"),
            ]
        )
        return g

    def test_hub_outranks_every_leaf(self):
        scores = pagerank(self._star())
        leaves = ("leaf-a", "leaf-b", "leaf-c")
        for leaf in leaves:
            assert scores["hub"] > scores[leaf]

    def test_vector_sums_to_one(self):
        scores = pagerank(self._star())
        assert sum(scores.values()) == pytest.approx(1.0, abs=1e-9)


class TestDanglingNodeMassConservation:
    """A node with no out-edges must not leak probability mass."""

    def _with_dangling(self) -> NetworkXGraph:
        g = directed_graph()
        # "sink" has no out-edge; its mass must be redistributed, not lost.
        g.add_edges_from([("a", "b"), ("b", "sink")])
        g.add_node("sink")
        return g

    def test_mass_is_conserved(self):
        scores = pagerank(self._with_dangling())
        assert "sink" in scores
        assert sum(scores.values()) == pytest.approx(1.0, abs=1e-9)


class TestDeterminismUnderInsertionOrder:
    """Edge insertion order must not change scores (hash-seed regression guard)."""

    def _edges(self) -> list[tuple[str, str]]:
        return [
            ("a", "b"),
            ("b", "c"),
            ("c", "a"),
            ("a", "c"),
            ("d", "a"),
            ("b", "d"),
        ]

    def test_reversed_insertion_order_gives_identical_scores(self):
        forward = directed_graph()
        forward.add_edges_from(self._edges())
        reverse = directed_graph()
        reverse.add_edges_from(list(reversed(self._edges())))

        forward_scores = pagerank(forward)
        reverse_scores = pagerank(reverse)

        assert set(forward_scores) == set(reverse_scores)
        for node in forward_scores:
            # Bit-identical, not merely close: the computation is a pure
            # function of the graph contents, independent of node/edge order.
            assert forward_scores[node] == reverse_scores[node]
