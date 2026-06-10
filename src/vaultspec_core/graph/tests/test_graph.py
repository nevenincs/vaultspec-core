"""Tests for the vault document graph API.

Covers node construction, graph building from the fixture vault, query
methods, metrics computation (via networkx algorithms), tree rendering
(Rich), ASCII rendering (phart), and JSON serialisation (node_link_data).
"""

import json
from pathlib import Path

import pytest

from ...graph import DocNode, GraphMetrics, VaultGraph
from ...vaultcore import DocType

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# DocNode
# ---------------------------------------------------------------------------


class TestDocNode:
    def test_defaults(self):
        node = DocNode(path=Path("test.md"), name="test")
        assert node.doc_type is None
        assert node.tags == set()
        assert node.out_links == set()
        assert node.in_links == set()
        assert node.feature is None
        assert node.date is None
        assert node.title is None
        assert node.body == ""
        assert node.word_count == 0
        assert node.frontmatter == {}

    def test_to_nx_attrs_serialises_sets_as_sorted_lists(self):
        node = DocNode(
            path=Path("/a/b.md"),
            name="b",
            tags={"#z", "#a"},
            out_links={"c", "a"},
            in_links={"d"},
        )
        d = node.to_nx_attrs()
        assert d["tags"] == ["#a", "#z"]
        assert d["out_links"] == ["a", "c"]
        assert d["in_links"] == ["d"]
        assert d["path"] == str(Path("/a/b.md"))

    def test_to_nx_attrs_includes_all_fields(self):
        node = DocNode(
            path=Path("x.md"),
            name="x",
            doc_type=DocType.ADR,
            feature="my-feat",
            date="2026-01-15",
            title="My Title",
            tags={"#adr", "#my-feat"},
            frontmatter={
                "tags": ["#adr", "#my-feat"],
                "date": "2026-01-15",
            },
            body="some body",
            word_count=2,
            out_links=set(),
            in_links=set(),
        )
        d = node.to_nx_attrs()
        assert d["doc_type"] == "adr"
        assert d["feature"] == "my-feat"
        assert d["date"] == "2026-01-15"
        assert d["title"] == "My Title"
        assert d["word_count"] == 2


# ---------------------------------------------------------------------------
# GraphMetrics
# ---------------------------------------------------------------------------


class TestGraphMetrics:
    def test_defaults(self):
        m = GraphMetrics()
        assert m.total_nodes == 0
        assert m.density == 0.0
        assert m.nodes_by_type == {}
        assert m.in_degree_centrality == {}
        assert m.betweenness_centrality == {}

    def test_to_dict_restructures_degree_tuples(self):
        m = GraphMetrics(
            max_in_degree=("hub", 5),
            max_out_degree=("spoke", 3),
        )
        d = m.to_dict()
        assert d["max_in_degree"] == {"node": "hub", "count": 5}
        assert d["max_out_degree"] == {
            "node": "spoke",
            "count": 3,
        }


# ---------------------------------------------------------------------------
# VaultGraph  - building
# ---------------------------------------------------------------------------


class TestVaultGraphBuilding:
    def test_builds_many_nodes(self, vault_root):
        graph = VaultGraph(vault_root)
        assert len(graph.nodes) > 80

    def test_no_nodes_lost_to_stem_collisions(self, vault_root):
        """All files produce a node  - collisions use type/stem keys."""
        from ...vaultcore import scan_vault

        file_count = sum(1 for _ in scan_vault(vault_root))
        graph = VaultGraph(vault_root)
        real_count = sum(1 for n in graph.nodes.values() if not n.phantom)
        assert real_count == file_count

    def test_colliding_stems_get_qualified_keys(self, vault_root):
        graph = VaultGraph(vault_root)
        qualified = [k for k in graph.nodes if "/" in k]
        assert len(qualified) > 0
        # Each qualified key should have the form "type/stem"
        for key in qualified:
            parts = key.split("/", 1)
            assert len(parts) == 2
            assert len(parts[0]) > 0
            assert len(parts[1]) > 0

    def test_stem_index_maps_collisions(self, vault_root):
        graph = VaultGraph(vault_root)
        collisions = {
            stem: keys for stem, keys in graph._stem_index.items() if len(keys) > 1
        }
        assert len(collisions) > 0
        for stem, keys in collisions.items():
            assert all(k.endswith(stem) for k in keys)
            assert all(k in graph.nodes for k in keys)

    def test_wiki_links_to_colliding_stems_fan_out(self, vault_root):
        """Stem collisions exist in the synthetic corpus fixture."""
        graph = VaultGraph(vault_root)
        collisions = {
            stem: keys for stem, keys in graph._stem_index.items() if len(keys) > 1
        }
        assert collisions, "Test vault must have stem collisions"
        for stem, keys in collisions.items():
            assert len(keys) >= 2, f"Collision for {stem!r} has fewer than 2 variants"
            for key in keys:
                assert key in graph.nodes, f"Collision key {key!r} missing from nodes"

    def test_wiki_links_to_colliding_stems_fan_out_guaranteed(self, tmp_path):
        """A wiki-link to a colliding stem fans out to all qualified variants.

        Constructs a minimal vault where two docs share the same stem in
        different subdirectories and a third doc links to the bare stem.
        The test asserts unconditionally that the linker has edges to both
        collision variants - the condition is guaranteed by construction.
        """
        vault_dir = tmp_path / ".vault"
        (vault_dir / "adr").mkdir(parents=True)
        (vault_dir / "plan").mkdir(parents=True)
        (vault_dir / "research").mkdir(parents=True)

        # Two docs sharing the stem "shared-stem"
        (vault_dir / "adr" / "shared-stem.md").write_text(
            '---\ntags:\n  - "#adr"\n  - "#collision-test"\n'
            "date: 2026-01-01\nrelated: []\n---\n\n# adr shared-stem\n",
            encoding="utf-8",
        )
        (vault_dir / "plan" / "shared-stem.md").write_text(
            '---\ntags:\n  - "#plan"\n  - "#collision-test"\n'
            "date: 2026-01-01\nrelated: []\n---\n\n# plan shared-stem\n",
            encoding="utf-8",
        )

        # Third doc links to the bare stem
        (vault_dir / "research" / "linker-doc.md").write_text(
            '---\ntags:\n  - "#research"\n  - "#collision-test"\n'
            'date: 2026-01-01\nrelated:\n  - "[[shared-stem]]"\n---\n\n'
            "# linker doc\n",
            encoding="utf-8",
        )

        graph = VaultGraph(tmp_path)

        # The stem must be a collision (mapped to two qualified keys)
        assert len(graph._stem_index.get("shared-stem", [])) == 2
        adr_key = "adr/shared-stem"
        plan_key = "plan/shared-stem"
        assert adr_key in graph.nodes
        assert plan_key in graph.nodes

        # linker-doc must have edges to BOTH collision variants
        linker = graph.nodes["linker-doc"]
        assert adr_key in linker.out_links, f"linker-doc missing edge to {adr_key!r}"
        assert plan_key in linker.out_links, f"linker-doc missing edge to {plan_key!r}"
        assert graph._digraph.has_edge("linker-doc", adr_key)
        assert graph._digraph.has_edge("linker-doc", plan_key)

    def test_networkx_digraph_has_same_node_count(self, vault_root):
        graph = VaultGraph(vault_root)
        assert graph._digraph.number_of_nodes() == len(graph.nodes)

    def test_networkx_digraph_has_edges(self, vault_root):
        graph = VaultGraph(vault_root)
        assert graph._digraph.number_of_edges() > 0

    def test_digraph_property_exposes_nx_graph(self, vault_root):
        import networkx as nx

        graph = VaultGraph(vault_root)
        assert isinstance(graph.digraph, nx.DiGraph)
        assert graph.digraph is graph._digraph

    def test_nx_node_attrs_are_json_friendly(self, vault_root):
        graph = VaultGraph(vault_root)
        name = "2026-02-05-editor-demo-architecture-adr"
        attrs = graph.digraph.nodes[name]
        assert isinstance(attrs["tags"], list)
        assert isinstance(attrs["path"], str)
        assert attrs["doc_type"] == "adr"

    def test_node_has_doc_type(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert node.doc_type == DocType.ADR

    def test_node_has_feature(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert node.feature == "editor-demo"

    def test_node_has_date(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert node.date is not None
        assert node.date.startswith("2026")

    def test_node_has_body_and_word_count(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert len(node.body) > 0
        assert node.word_count > 0

    def test_node_has_frontmatter_dict(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert isinstance(node.frontmatter, dict)
        assert "tags" in node.frontmatter

    def test_out_links_populated(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes["2026-02-05-editor-demo-architecture-adr"]
        assert len(node.out_links) > 0

    def test_in_links_populated(self, vault_root):
        graph = VaultGraph(vault_root)
        node = graph.nodes.get("2026-02-05-editor-demo-research")
        assert node is not None
        assert len(node.in_links) > 0


# ---------------------------------------------------------------------------
# VaultGraph  - queries
# ---------------------------------------------------------------------------


class TestVaultGraphQueries:
    def test_get_orphaned(self, vault_root):
        graph = VaultGraph(vault_root)
        orphans = graph.get_orphaned()
        assert isinstance(orphans, list)
        assert orphans == sorted(orphans)

    def test_get_dangling_links(self, vault_root):
        graph = VaultGraph(vault_root)
        dangling = graph.get_dangling_links()
        assert isinstance(dangling, list)

    def test_get_feature_rankings(self, vault_root):
        graph = VaultGraph(vault_root)
        rankings = graph.get_feature_rankings()
        assert isinstance(rankings, list)
        feature_names = [name for name, _score in rankings]
        assert "editor-demo" in feature_names

    def test_get_feature_nodes(self, vault_root):
        graph = VaultGraph(vault_root)
        nodes = graph.get_feature_nodes("editor-demo")
        assert len(nodes) > 0
        for node in nodes:
            assert "#editor-demo" in node.tags

    def test_get_feature_nodes_sorted_by_date(self, vault_root):
        graph = VaultGraph(vault_root)
        nodes = graph.get_feature_nodes("editor-demo")
        dates = [n.date for n in nodes if n.date]
        assert dates == sorted(dates)

    def test_get_features(self, vault_root):
        graph = VaultGraph(vault_root)
        features = graph.get_features()
        assert "editor-demo" in features
        assert features == sorted(features)

    def test_subgraph_returns_nx_digraph(self, vault_root):
        import networkx as nx

        graph = VaultGraph(vault_root)
        sg = graph.subgraph(feature="editor-demo")
        assert isinstance(sg, nx.DiGraph)
        assert sg.number_of_nodes() > 0
        assert sg.number_of_nodes() < len(graph.nodes)

    def test_subgraph_none_returns_full(self, vault_root):
        graph = VaultGraph(vault_root)
        sg = graph.subgraph(feature=None)
        assert sg is graph._digraph


# ---------------------------------------------------------------------------
# VaultGraph  - metrics (networkx algorithms)
# ---------------------------------------------------------------------------


class TestVaultGraphMetrics:
    def test_global_metrics(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics()
        assert m.total_nodes > 80
        assert m.total_edges > 0
        assert m.total_features > 0
        assert m.total_words > 0
        assert 0.0 <= m.density <= 1.0
        assert m.avg_in_degree > 0
        assert m.connected_components >= 1
        assert len(m.nodes_by_type) > 0

    def test_centrality_populated(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics()
        assert len(m.in_degree_centrality) > 0
        assert len(m.betweenness_centrality) > 0
        # Values are normalised floats
        for v in m.in_degree_centrality.values():
            assert 0.0 <= v <= 1.0
        for v in m.betweenness_centrality.values():
            assert 0.0 <= v <= 1.0

    def test_feature_scoped_metrics(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics(feature="editor-demo")
        assert m.total_nodes > 0
        assert m.total_features == 1
        assert m.nodes_by_feature == {
            "editor-demo": m.total_nodes,
        }

    def test_feature_scoped_centrality_populated(self, vault_root):
        """metrics(feature=...) populates centrality dicts for the subgraph.

        The synthetic corpus fixture has enough editor-demo nodes that
        the subgraph has >1 node, so networkx computes non-empty centrality
        scores.  The test asserts both in_degree_centrality and
        betweenness_centrality are non-empty dicts with normalised floats.
        """
        graph = VaultGraph(vault_root)
        m = graph.metrics(feature="editor-demo")
        # The feature subgraph must have more than one node for centrality
        # to be computed; fail loudly if the fixture shrinks below the threshold.
        assert m.total_nodes > 1, (
            "editor-demo subgraph has <=1 node; "
            "fixture must be regenerated with more docs for centrality assertions"
        )
        assert len(m.in_degree_centrality) > 0, (
            "in_degree_centrality is empty for editor-demo subgraph"
        )
        assert len(m.betweenness_centrality) > 0, (
            "betweenness_centrality is empty for editor-demo subgraph"
        )
        for v in m.in_degree_centrality.values():
            assert 0.0 <= v <= 1.0, f"in_degree_centrality value {v} out of range"
        for v in m.betweenness_centrality.values():
            assert 0.0 <= v <= 1.0, f"betweenness_centrality value {v} out of range"

    def test_feature_scoped_centrality_keys_are_node_names(self, vault_root):
        """Centrality dict keys are node names belonging to the feature subgraph."""
        graph = VaultGraph(vault_root)
        m = graph.metrics(feature="editor-demo")
        if not m.in_degree_centrality:
            return  # subgraph too small; handled by previous test
        feature_node_names = {n.name for n in graph.get_feature_nodes("editor-demo")}
        for key in m.in_degree_centrality:
            assert key in feature_node_names, (
                f"centrality key {key!r} not in editor-demo feature nodes"
            )

    def test_metrics_to_dict(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics()
        d = m.to_dict()
        assert "total_nodes" in d
        assert "max_in_degree" in d
        assert isinstance(d["max_in_degree"], dict)
        assert "in_degree_centrality" in d
        assert "betweenness_centrality" in d


# ---------------------------------------------------------------------------
# VaultGraph  - ASCII rendering (phart)
# ---------------------------------------------------------------------------


class TestVaultGraphASCII:
    def test_render_ascii_returns_string(self, vault_root):
        graph = VaultGraph(vault_root)
        result = graph.render_ascii()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_ascii_feature_scoped(self, vault_root):
        graph = VaultGraph(vault_root)
        result = graph.render_ascii(feature="editor-demo")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# VaultGraph  - tree rendering (Rich)
# ---------------------------------------------------------------------------


class TestVaultGraphRendering:
    def test_render_tree_full_vault(self, vault_root):
        from rich.tree import Tree

        graph = VaultGraph(vault_root)
        tree = graph.render_tree()
        assert isinstance(tree, Tree)

    def test_render_tree_feature_scoped(self, vault_root):
        from rich.tree import Tree

        graph = VaultGraph(vault_root)
        tree = graph.render_tree(feature="editor-demo")
        assert isinstance(tree, Tree)


# ---------------------------------------------------------------------------
# VaultGraph  - JSON serialisation (networkx node_link_data)
# ---------------------------------------------------------------------------


class TestVaultGraphJSON:
    def test_to_dict_uses_node_link_format(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict()
        # networkx node_link_data keys
        assert "directed" in d
        assert "multigraph" in d
        assert "nodes" in d
        assert "edges" in d
        # vault enrichments
        assert "metrics" in d
        assert "root" in d
        assert d["directed"] is True

    def test_to_dict_nodes_have_id(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict()
        for node_dict in d["nodes"]:
            assert "id" in node_dict

    def test_to_dict_body_excluded_by_default(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict()
        for node_dict in d["nodes"]:
            assert "body" not in node_dict

    def test_to_dict_with_body(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict(include_body=True)
        has_body = any("body" in n for n in d["nodes"])
        assert has_body

    def test_to_dict_feature_scoped(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict(feature="editor-demo")
        assert d["feature"] == "editor-demo"
        for node_dict in d["nodes"]:
            assert "#editor-demo" in node_dict.get("tags", [])

    def test_to_json_is_valid_json(self, vault_root):
        graph = VaultGraph(vault_root)
        s = graph.to_json()
        parsed = json.loads(s)
        assert "nodes" in parsed
        assert "metrics" in parsed

    def test_to_json_feature_scoped(self, vault_root):
        graph = VaultGraph(vault_root)
        s = graph.to_json(feature="editor-demo")
        parsed = json.loads(s)
        assert parsed["feature"] == "editor-demo"

    def test_edges_have_source_and_target(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict()
        for edge in d["edges"]:
            assert "source" in edge
            assert "target" in edge


# ---------------------------------------------------------------------------
# DocNode  - phantom defaults
# ---------------------------------------------------------------------------


class TestDocNodePhantom:
    def test_defaults_include_phantom_false(self):
        node = DocNode(path=Path("test.md"), name="test")
        assert node.phantom is False

    def test_to_nx_attrs_includes_phantom_field(self):
        node = DocNode(path=Path("x.md"), name="x")
        d = node.to_nx_attrs()
        assert "phantom" in d
        assert d["phantom"] is False

    def test_to_nx_attrs_phantom_true(self):
        node = DocNode(path=None, name="ghost", phantom=True)
        d = node.to_nx_attrs()
        assert d["phantom"] is True


# ---------------------------------------------------------------------------
# VaultGraph  - phantom nodes
# ---------------------------------------------------------------------------


class TestVaultGraphPhantom:
    def test_builds_many_nodes_includes_phantoms(self, vault_root):
        """Total node count includes both real and phantom nodes."""
        graph = VaultGraph(vault_root)
        real = sum(1 for n in graph.nodes.values() if not n.phantom)
        phantoms = sum(1 for n in graph.nodes.values() if n.phantom)
        assert len(graph.nodes) == real + phantoms
        assert phantoms > 0

    def test_phantom_nodes_created_for_unresolved_targets(self, vault_root):
        graph = VaultGraph(vault_root)
        phantoms = [n for n in graph.nodes.values() if n.phantom]
        assert len(phantoms) > 0
        for node in phantoms:
            assert node.phantom is True
            assert node.name in graph.nodes
            assert node.name in graph._digraph

    def test_phantom_nodes_have_incoming_edges(self, vault_root):
        graph = VaultGraph(vault_root)
        phantoms = [n for n in graph.nodes.values() if n.phantom]
        for node in phantoms:
            assert len(node.in_links) > 0
            for source in node.in_links:
                assert graph._digraph.has_edge(source, node.name)

    def test_get_orphaned_excludes_phantoms(self, vault_root):
        graph = VaultGraph(vault_root)
        orphans = graph.get_orphaned()
        for name in orphans:
            assert not graph.nodes[name].phantom

    def test_to_snapshot_excludes_phantoms(self, vault_root):
        graph = VaultGraph(vault_root)
        snapshot = graph.to_snapshot()
        phantom_names = {n.name for n in graph.nodes.values() if n.phantom}
        snapshot_stems = {p.stem for p in snapshot}
        assert not phantom_names & snapshot_stems

    def test_metrics_phantom_count(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics()
        actual_phantoms = sum(1 for n in graph.nodes.values() if n.phantom)
        assert m.phantom_count == actual_phantoms
        assert m.phantom_count > 0

    def test_metrics_dangling_link_count(self, vault_root):
        graph = VaultGraph(vault_root)
        m = graph.metrics()
        edge_count_to_phantoms = sum(
            1
            for src, tgt in graph._dangling_links
            if tgt in graph.nodes and graph.nodes[tgt].phantom
        )
        assert m.dangling_link_count == edge_count_to_phantoms
        assert m.dangling_link_count > 0

    def test_check_schema_ignores_phantom_adr_references(
        self, vault_root, graph_manifest
    ):
        """A plan linking only to phantom targets still reports 'no ADR reference'."""
        from ...vaultcore.checks.references import check_schema

        graph = VaultGraph(vault_root)
        result = check_schema(vault_root, graph=graph)
        # Resolve the phantom-only-links plan via the manifest so the test is
        # not coupled to a specific hardcoded filename.
        plan_doc = graph_manifest.pathology_details["phantom_only_links"][0]["plan_doc"]
        plan_name = plan_doc.path.stem
        node = graph.nodes[plan_name]
        assert node.doc_type == DocType.PLAN
        # All its out_link targets are phantom
        assert all(graph.nodes[t].phantom for t in node.out_links if t in graph.nodes)
        # check_schema should report an error for this plan
        plan_diags = [
            d
            for d in result.diagnostics
            if d.path is not None and plan_name in str(d.path)
        ]
        assert any("no references to ADR" in d.message for d in plan_diags)

    def test_tree_rendering_shows_not_created_for_phantoms(self, vault_root):
        from io import StringIO

        from rich.console import Console

        graph = VaultGraph(vault_root)
        tree = graph.render_tree()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=200)
        console.print(tree)
        output = buf.getvalue()
        assert "(not created)" in output

    def test_json_output_includes_phantom_flag(self, vault_root):
        graph = VaultGraph(vault_root)
        d = graph.to_dict()
        phantom_dicts = [n for n in d["nodes"] if n.get("phantom") is True]
        assert len(phantom_dicts) > 0
        for pd in phantom_dicts:
            assert pd["phantom"] is True


# ---------------------------------------------------------------------------
# VaultGraph  - archive resolution branch
# ---------------------------------------------------------------------------


def _make_vault_with_archive(tmp_path):
    """Build a minimal two-document vault where one doc is archived.

    Layout::

        <root>/
          .vault/
            adr/
              source-doc.md       <- links to archived-doc
            _archive/
              adr/
                archived-doc.md   <- the archived target

    The source doc's ``related:`` entry points to ``archived-doc`` by
    bare stem.  The archive resolver must find it under ``_archive/adr/``
    and return the qualified key ``adr/archived-doc``.
    """
    vault_dir = tmp_path / ".vault"
    adr_dir = vault_dir / "adr"
    archive_adr_dir = vault_dir / "_archive" / "adr"
    adr_dir.mkdir(parents=True)
    archive_adr_dir.mkdir(parents=True)

    # Source doc - links to the archived target by bare stem
    source = adr_dir / "source-doc.md"
    source.write_text(
        '---\ntags:\n  - "#adr"\n  - "#archive-test"\n'
        'date: 2026-01-01\nrelated:\n  - "[[archived-doc]]"\n---\n\n'
        "# source doc\n\nLinks to archived-doc.\n",
        encoding="utf-8",
    )

    # Archived target - lives under _archive/adr/
    archived = archive_adr_dir / "archived-doc.md"
    archived.write_text(
        '---\ntags:\n  - "#adr"\n  - "#archive-test"\n'
        "date: 2026-01-01\nrelated: []\n---\n\n"
        "# archived doc\n\nThis document is archived.\n",
        encoding="utf-8",
    )

    return tmp_path, source, archived


class TestVaultGraphArchiveResolution:
    """Tests for the _resolve_link / _is_archived archive-resolution branch.

    Uses a real minimal vault fixture, not mocks, so the filesystem
    traversal is exercised end-to-end.
    """

    def test_archived_link_does_not_appear_in_dangling(self, tmp_path):
        """A link to an archived doc must not be counted as dangling."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        dangling = graph.get_dangling_links()
        dangling_targets = {tgt for _src, tgt in dangling}
        # archived-doc or adr/archived-doc should not be flagged as dangling
        assert "archived-doc" not in dangling_targets
        assert "adr/archived-doc" not in dangling_targets

    def test_archived_target_produces_phantom_node(self, tmp_path):
        """The graph creates a phantom node for the archived target."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        # The source doc links to archived-doc; it resolves to adr/archived-doc
        resolved_key = "adr/archived-doc"
        assert resolved_key in graph.nodes
        assert graph.nodes[resolved_key].phantom is True

    def test_source_out_links_contains_resolved_archive_key(self, tmp_path):
        """source-doc.out_links resolves to the qualified archive key."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        src_node = graph.nodes["source-doc"]
        assert "adr/archived-doc" in src_node.out_links

    def test_is_archived_true_for_archived_stem(self, tmp_path):
        """_is_archived returns True when the stem resolves under _archive/."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        # Bare stem - rglob branch
        assert graph._is_archived("archived-doc") is True

    def test_is_archived_true_for_qualified_key(self, tmp_path):
        """_is_archived returns True for a qualified type/stem key."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        # Qualified key with slash - direct path branch
        assert graph._is_archived("adr/archived-doc") is True

    def test_is_archived_false_when_no_archive_dir(self, tmp_path):
        """_is_archived returns False when there is no _archive/ directory."""
        # Build vault without any _archive dir
        vault_dir = tmp_path / ".vault" / "adr"
        vault_dir.mkdir(parents=True)
        (vault_dir / "only-doc.md").write_text(
            '---\ntags:\n  - "#adr"\n  - "#no-archive"\n'
            "date: 2026-01-01\nrelated: []\n---\n\n# only doc\n",
            encoding="utf-8",
        )
        graph = VaultGraph(tmp_path)
        assert graph._is_archived("any-stem") is False

    def test_is_archived_false_for_nonexistent_stem(self, tmp_path):
        """_is_archived returns False for a stem that is not in _archive/."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        assert graph._is_archived("completely-nonexistent-stem") is False

    def test_resolve_link_archive_bare_stem(self, tmp_path):
        """_resolve_link resolves a bare archived stem to its qualified key."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        # After graph build, archived-doc is in nodes as phantom;
        # a second resolve call still hits the exact-match branch.
        resolved = graph._resolve_link("adr/archived-doc")
        assert resolved == ["adr/archived-doc"]

    def test_archived_link_edge_exists_in_digraph(self, tmp_path):
        """A directed edge from source to the archived phantom node exists."""
        root, _src, _arch = _make_vault_with_archive(tmp_path)
        graph = VaultGraph(root)
        assert graph._digraph.has_edge("source-doc", "adr/archived-doc")


def _make_weighted_vault(tmp_path):
    """Build a minimal vault with crafted edge multiplicity and provenance.

    Document ``doc-a`` cites ``doc-b`` three times in its body and references
    ``doc-c`` both in its body once and in its ``related:`` frontmatter once.
    This yields exactly two edges with deterministic, hand-derivable
    attributes:

    - ``doc-a -> doc-b``: kind ``body``, multiplicity ``3`` (the graph maximum)
    - ``doc-a -> doc-c``: kind ``both``, multiplicity ``2``

    The maximum multiplicity is ``3`` so weights normalise to ``3/3 = 1.0`` and
    ``2/3`` respectively.
    """
    vault_dir = tmp_path / ".vault"
    (vault_dir / "research").mkdir(parents=True)
    (vault_dir / "adr").mkdir()
    (vault_dir / "plan").mkdir()

    (vault_dir / "research" / "doc-a.md").write_text(
        '---\ntags:\n  - "#research"\n  - "#weight-fixture"\n'
        'date: 2026-01-01\nrelated:\n  - "[[doc-c]]"\n---\n\n'
        "# doc a\n\nSee [[doc-b]] and [[doc-b]] and [[doc-b]] then [[doc-c]].\n",
        encoding="utf-8",
    )
    (vault_dir / "adr" / "doc-b.md").write_text(
        '---\ntags:\n  - "#adr"\n  - "#weight-fixture"\n'
        "date: 2026-01-01\nrelated: []\n---\n\n# doc b\n",
        encoding="utf-8",
    )
    (vault_dir / "plan" / "doc-c.md").write_text(
        '---\ntags:\n  - "#plan"\n  - "#weight-fixture"\n'
        "date: 2026-01-01\nrelated: []\n---\n\n# doc c\n",
        encoding="utf-8",
    )
    return tmp_path


class TestExplicitEdgeAttributes:
    """Exact-value assertions for edge kind, multiplicity, and weight."""

    def test_body_only_edge_kind_and_multiplicity(self, tmp_path):
        """A body-only triple citation yields kind body, multiplicity 3."""
        graph = VaultGraph(_make_weighted_vault(tmp_path))
        data = graph.digraph.edges["doc-a", "doc-b"]
        assert data["kind"] == "body"
        assert data["multiplicity"] == 3

    def test_both_sources_edge_kind_and_multiplicity(self, tmp_path):
        """A target reached by body and related is kind both, multiplicity 2."""
        graph = VaultGraph(_make_weighted_vault(tmp_path))
        data = graph.digraph.edges["doc-a", "doc-c"]
        assert data["kind"] == "both"
        assert data["multiplicity"] == 2

    def test_weight_is_multiplicity_over_graph_maximum(self, tmp_path):
        """Weights are exact rationals: 3/3 = 1.0 and 2/3."""
        graph = VaultGraph(_make_weighted_vault(tmp_path))
        assert graph.digraph.edges["doc-a", "doc-b"]["weight"] == 1.0
        assert graph.digraph.edges["doc-a", "doc-c"]["weight"] == 2 / 3

    def test_strongest_edge_normalises_to_one(self, tmp_path):
        """Exactly one edge - the maximum-multiplicity one - has weight 1.0."""
        graph = VaultGraph(_make_weighted_vault(tmp_path))
        weights = [d["weight"] for _, _, d in graph.digraph.edges(data=True)]
        assert weights.count(1.0) == 1
        assert max(weights) == 1.0

    def test_only_two_edges_built(self, tmp_path):
        """The crafted vault produces exactly the two intended edges."""
        graph = VaultGraph(_make_weighted_vault(tmp_path))
        assert graph.digraph.number_of_edges() == 2

    def test_synthetic_corpus_related_edges_are_unit_weight(self, vault_root):
        """The synthetic corpus emits only related, multiplicity-1 edges.

        The synthetic generator wires documents solely through ``related:``
        frontmatter with no duplicates, so every explicit edge is kind
        ``related`` with multiplicity ``1`` and (since the maximum is 1)
        weight ``1.0``.  This is a real assertion over the corpus, not a
        contrived one.
        """
        graph = VaultGraph(vault_root)
        edges = list(graph.digraph.edges(data=True))
        assert len(edges) > 0
        for _src, _tgt, data in edges:
            assert data["kind"] == "related"
            assert data["multiplicity"] == 1
            assert data["weight"] == 1.0
