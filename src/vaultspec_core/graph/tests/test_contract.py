"""Full-envelope v2 contract test for the graph JSON output.

Asserts the complete shape of the ``vaultspec.vault.graph.v2`` envelope
produced by ``VaultGraph.to_dict`` wrapped in ``json_envelope(..., version=2)``.
The test is designed to fail if any field is added, removed, or renamed
without a corresponding schema version bump.
"""

import json
from typing import Any

import pytest

from ...cli.rendering import json_envelope
from ...graph import VaultGraph

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# Expected field sets - update these when the schema version bumps, not
# when tests fail on an incidental refactor that does NOT change the contract.
# ---------------------------------------------------------------------------

_EXPECTED_ENVELOPE_KEYS = frozenset({"schema", "status", "data"})

_EXPECTED_DATA_KEYS = frozenset(
    {
        "directed",
        "multigraph",
        "graph",
        "nodes",
        "edges",
        "derived_edges",
        "root",
        "feature",
        "metrics",
    }
)

_EXPECTED_NODE_FIELDS = frozenset(
    {
        "id",
        "name",
        "path",
        "doc_type",
        "feature",
        "date",
        "modified",
        "title",
        "tags",
        "frontmatter",
        "word_count",
        "out_links",
        "in_links",
        "phantom",
        "pagerank",
        "in_degree",
    }
)

_EXPECTED_EDGE_FIELDS = frozenset(
    {
        "source",
        "target",
        "kind",
        "multiplicity",
        "weight",
    }
)

_EXPECTED_METRICS_KEYS = frozenset(
    {
        "total_nodes",
        "total_edges",
        "total_features",
        "total_words",
        "density",
        "avg_in_degree",
        "avg_out_degree",
        "max_in_degree",
        "max_out_degree",
        "in_degree_centrality",
        "betweenness_centrality",
        "phantom_count",
        "orphan_count",
        "dangling_link_count",
        "connected_components",
        "nodes_by_type",
        "nodes_by_feature",
    }
)


class TestGraphEnvelopeV2Contract:
    """Contract assertions for the vaultspec.vault.graph.v2 envelope shape.

    Any change to the envelope, node, edge, or metrics shape that does not
    update ``_EXPECTED_*`` constants in this module is a contract violation
    and should be rejected until the schema version is bumped.
    """

    def test_schema_string(self, vault_root):
        """Envelope schema must be exactly vaultspec.vault.graph.v2."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(),
            version=2,
        )
        assert envelope["schema"] == "vaultspec.vault.graph.v2"

    def test_envelope_top_level_keys(self, vault_root):
        """Envelope has exactly schema, status, and data."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(),
            version=2,
        )
        assert frozenset(envelope.keys()) == _EXPECTED_ENVELOPE_KEYS

    def test_status_key_present(self, vault_root):
        """Status field is present and non-empty."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(),
            version=2,
        )
        assert envelope["status"] == "unchanged"

    def test_data_keys(self, vault_root):
        """data payload has exactly the expected top-level keys."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(),
            version=2,
        )
        data = envelope["data"]
        assert isinstance(data, dict)
        assert frozenset(data.keys()) == _EXPECTED_DATA_KEYS

    def _data(self, vault_root: Any, feature: str | None = None) -> dict[str, Any]:
        """Build the envelope and return its data payload as a typed dict."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(feature=feature),
            version=2,
        )
        return dict(envelope)

    def test_every_node_has_required_fields(self, vault_root):
        """Every node dict carries exactly the expected field set."""
        envelope = self._data(vault_root)
        nodes: list[dict[str, Any]] = envelope["data"]["nodes"]  # type: ignore[index]
        assert len(nodes) > 0, "No nodes in graph - corpus generation failed"
        for node in nodes:
            missing = _EXPECTED_NODE_FIELDS - frozenset(node.keys())
            extra = frozenset(node.keys()) - _EXPECTED_NODE_FIELDS
            assert not missing, f"Node {node.get('id')!r} missing fields: {missing}"
            assert not extra, f"Node {node.get('id')!r} unexpected fields: {extra}"

    def test_every_edge_has_required_fields(self, vault_root):
        """Every edge dict carries exactly source and target."""
        envelope = self._data(vault_root)
        edges: list[dict[str, Any]] = envelope["data"]["edges"]  # type: ignore[index]
        assert len(edges) > 0, "No edges in graph - corpus generation failed"
        for edge in edges:
            missing = _EXPECTED_EDGE_FIELDS - frozenset(edge.keys())
            extra = frozenset(edge.keys()) - _EXPECTED_EDGE_FIELDS
            assert not missing, f"Edge {edge!r} missing fields: {missing}"
            assert not extra, f"Edge {edge!r} unexpected fields: {extra}"

    def test_metrics_keys(self, vault_root):
        """metrics dict carries exactly the expected key set."""
        envelope = self._data(vault_root)
        metrics: dict[str, Any] = envelope["data"]["metrics"]  # type: ignore[index]
        assert isinstance(metrics, dict)
        missing = _EXPECTED_METRICS_KEYS - frozenset(metrics.keys())
        extra = frozenset(metrics.keys()) - _EXPECTED_METRICS_KEYS
        assert not missing, f"metrics missing keys: {missing}"
        assert not extra, f"metrics unexpected keys: {extra}"

    def test_envelope_is_json_serialisable(self, vault_root):
        """Entire envelope round-trips through json.dumps / json.loads."""
        graph = VaultGraph(vault_root)
        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(),
            version=2,
        )
        serialised = json.dumps(envelope, default=str)
        parsed = json.loads(serialised)
        assert parsed["schema"] == "vaultspec.vault.graph.v2"

    def test_directed_graph_flag(self, vault_root):
        """data.directed must be True - the graph is directed."""
        envelope = self._data(vault_root)
        data: dict[str, Any] = envelope["data"]  # type: ignore[index]
        assert data["directed"] is True

    def test_metrics_max_degree_shape(self, vault_root):
        """max_in_degree and max_out_degree are {node, count} dicts."""
        envelope = self._data(vault_root)
        metrics: dict[str, Any] = envelope["data"]["metrics"]  # type: ignore[index]
        for field_name in ("max_in_degree", "max_out_degree"):
            value = metrics[field_name]
            assert isinstance(value, dict), f"{field_name} must be a dict"
            assert frozenset(value.keys()) == frozenset({"node", "count"}), (
                f"{field_name} must have exactly 'node' and 'count' keys"
            )

    def test_feature_scoped_envelope_shape(self, vault_root):
        """Feature-scoped to_dict also produces the full v2 shape."""
        envelope = self._data(vault_root, feature="editor-demo")
        assert envelope["schema"] == "vaultspec.vault.graph.v2"
        data: dict[str, Any] = envelope["data"]  # type: ignore[index]
        assert data["feature"] == "editor-demo"
        # Nodes in a feature-scoped graph are all tagged with the feature
        nodes: list[dict[str, Any]] = data["nodes"]
        for node in nodes:
            assert "#editor-demo" in node["tags"]
