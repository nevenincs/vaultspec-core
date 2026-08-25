"""Build, query, and render the vault document relationship graph.

Turns ``vaultcore`` scanning, metadata parsing, and wiki-link extraction into
a queryable directed graph of ``.vault/`` documents backed by
``networkx.DiGraph``. Delegates construction to
:mod:`vaultspec_core.graph.building` (ingress read, cache round-trip, and the
assembly passes), rendering to ``phart`` (ASCII topology) and
:func:`~vaultspec_core.cli.rendering.render_tree` (box-free hierarchical tree),
and serialisation to :mod:`vaultspec_core.graph.api_export` over
``networkx.readwrite.json_graph``.

Example::

    graph = VaultGraph(root_dir)
    lines = graph.render_tree_lines(feature="my-feature")  # list[TreeLine]
    ascii = graph.render_ascii(feature="my-feature")       # phart ASCII
    data  = graph.to_dict(feature="my-feature")            # JSON-ready dict
    stats = graph.metrics()                                # GraphMetrics

Exports:
    :class:`DocNode`: Node carrying full frontmatter, body, and link metadata.
    :class:`GraphMetrics`: Computed shape and size statistics for the graph.
    :class:`VaultGraph`: Main entry point; instantiate with a vault root dir.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import networkx as nx

from ..vaultcore import DocType, scan_vault
from ..vaultcore.models import DocumentMetadata
from . import api_export, building, rendering
from .algorithms import betweenness_centrality, top_n
from .models import DocNode, EncodingIssue, GraphCounts, GraphMetrics
from .networkx_runtime import NetworkXGraph, directed_graph, ego_graph
from .networkx_runtime import density as graph_density

if TYPE_CHECKING:
    import pathlib

    from vaultspec_core.cli.rendering import TreeLine

    from ..vaultcore.checks._base import VaultSnapshot

logger = logging.getLogger(__name__)


__all__ = ["DocNode", "GraphMetrics", "VaultGraph"]

# ---------------------------------------------------------------------------
# VaultGraph
# ---------------------------------------------------------------------------


class VaultGraph:
    """Directed graph of vault documents linked by wiki-links and
    ``related:`` fields.

    Backed by a ``networkx.DiGraph`` for efficient traversal and
    algorithm access.  Each graph node stores serialisable attributes
    from its :class:`DocNode`, and each directed edge represents a
    wiki-link or ``related:`` reference.

    Every explicit edge carries three attributes set during build:

    - ``kind``: provenance of the reference, one of ``"body"`` (a body
      wiki-link only), ``"related"`` (a ``related:`` frontmatter entry
      only), or ``"both"`` (the target is reached by both sources).
    - ``multiplicity``: the total number of times the source references
      the target, summing body citations and ``related:`` entries.
    - ``weight``: ``multiplicity`` normalised against the maximum
      multiplicity of any edge in the graph, so the strongest edge has
      weight ``1.0``.  Derived/implicit relatedness never enters these
      edges; it is computed separately in
      :mod:`vaultspec_core.graph.derived`.

    Args:
        root_dir: Root directory of the vault to analyse.

    Example::

        graph = VaultGraph(Path("/my/project"))

        # ASCII graph in the terminal (via phart)
        print(graph.render_ascii(feature="auth"))

        # Rich hierarchical tree
        console.print(graph.render_tree(feature="auth"))

        # JSON export (networkx node-link format)
        print(graph.to_json())

        # Metrics (all via networkx algorithms)
        m = graph.metrics()
        print(f"Density: {m.density:.3f}")
    """

    def __init__(self, root_dir: pathlib.Path, *, use_cache: bool = True) -> None:
        self.root_dir = root_dir
        #: The git ref this graph was built from, or ``None`` for a
        #: working-tree build. Set only via :meth:`from_ref`.
        self.ref: str | None = None
        self.nodes: dict[str, DocNode] = {}
        self._digraph: NetworkXGraph = directed_graph()
        self._dangling_links: list[tuple[str, str]] = []
        self._stem_index: dict[str, list[str]] = {}
        self._raw_texts: dict[pathlib.Path, tuple[str, bool]] = {}
        self._encoding_issues: list[EncodingIssue] = []
        self._build_graph(use_cache=use_cache)

    @classmethod
    def from_ref(cls, root_dir: pathlib.Path, ref: str) -> VaultGraph:
        """Build a graph from the vault corpus at a git *ref*, without a checkout.

        Reads the vault documents from the git object database at *ref* (issue
        #160) instead of the working tree. The build runs with the graph cache
        disabled and the working-tree migration pass skipped - a read-only view
        of history must neither be served stale working-tree data nor write
        working-tree state (the ``ref-scoped-reads-bypass-worktree-cache``
        rule). Document-type classification reads each blob's tree path rather
        than a filesystem location, so the resulting graph is structurally
        identical to a working-tree build of the same corpus.

        Args:
            root_dir: Repository working directory (used for ``git -C`` and as
                the envelope ``root``).
            ref: A branch name, tag, or commit-ish to read the corpus from.

        Returns:
            A :class:`VaultGraph` over the corpus as it stood at *ref*.

        Raises:
            RefScanError: When *root_dir* is not a git repository or *ref*
                does not resolve to a commit.
        """
        import pathlib

        from ..config import get_config
        from .refscan import read_vault_at_ref

        graph = cls.__new__(cls)
        graph.root_dir = root_dir
        graph.ref = ref
        graph.nodes = {}
        graph._digraph = nx.DiGraph()
        graph._dangling_links = []
        graph._stem_index = {}
        graph._raw_texts = {}
        graph._encoding_issues = []

        docs_dir_name = pathlib.Path(get_config().docs_dir).name
        corpus = read_vault_at_ref(root_dir, ref, docs_dir_name)
        building.rebuild_from_corpus(graph, corpus, docs_dir_name)
        return graph

    # -- Construction --------------------------------------------------------

    def _build_graph(self, *, use_cache: bool = True) -> None:
        """Populate the graph, loading from the fingerprint cache when valid.

        Scans the vault once into a file list.  When *use_cache* is set and a
        cache file exists whose manifest passes the racily-clean validation
        (same file set, same per-file size and mtime, and a matching content
        hash for any file whose mtime is not older than the cache file's own
        mtime), the serialised canonical graph is loaded and the full parse is
        skipped.  On any divergence - a changed, added, or removed file, an
        absent cache, or a corrupt cache - the graph is rebuilt from the
        scanned files and the cache (manifest hashes included) is rewritten.

        Validation is stat-first: full content hashing happens only on the
        save path after a rebuild, never on the warm read, so the cache's own
        upkeep stays cheap relative to the parse it avoids.  A corrupt cache
        degrades silently to a full rebuild rather than crashing or serving
        stale data.

        Args:
            use_cache: When ``True`` (default), attempt a cache load before
                rebuilding and rewrite the cache after a rebuild.  When
                ``False``, ignore and do not write the cache (a forced fresh
                build).
        """
        from . import cache as cache_mod

        logger.info("Building vault graph from %s", self.root_dir)

        scanned_files = list(scan_vault(self.root_dir))
        path = cache_mod.cache_path(self.root_dir)

        if use_cache:
            payload = cache_mod.load(path)
            if payload is not None:
                try:
                    cache_mtime_ns: int | None = path.stat().st_mtime_ns
                except OSError:
                    cache_mtime_ns = None
                if cache_mod.validate(
                    payload.manifest,
                    scanned_files,
                    self.root_dir,
                    cache_mtime_ns=cache_mtime_ns,
                ):
                    logger.info("Graph cache hit at %s; skipping re-parse", path)
                    building.load_from_cache(self, payload)
                    return
            logger.info("Graph cache miss at %s; rebuilding", path)

        building.rebuild_from_files(self, scanned_files)

        if use_cache:
            cache_mod.save(
                path,
                cache_mod.fingerprint_vault(scanned_files, self.root_dir),
                building.to_cache_graph(self),
                self._dangling_links,
                [
                    (str(issue.path), issue.kind, issue.detail, issue.start)
                    for issue in self._encoding_issues
                ],
            )

    def ensure_raw_texts(self) -> None:
        """Guarantee :attr:`raw_texts` is populated for a working-tree graph.

        A cold build fills the raw-text map during its parse; a cache-hit
        build parses nothing, so a caller that needs document text (the
        check pipeline) invokes this to perform the run's single ingress
        read pass. A no-op when the map is already populated or when the
        graph is ref-scoped (checks do not run against history).
        """
        building.ensure_raw_texts(self)

    @property
    def raw_texts(self) -> dict[pathlib.Path, tuple[str, bool]]:
        """Per-document ``(normalised text, source_had_crlf)`` in scan order.

        Populated by a cold build or :meth:`ensure_raw_texts`; empty after a
        bare cache hit or for a ref-scoped graph.
        """
        return self._raw_texts

    @property
    def encoding_issues(self) -> list[EncodingIssue]:
        """Read and decode failures observed during the ingress read."""
        return self._encoding_issues

    # -- Direct networkx access ----------------------------------------------

    @property
    def digraph(self) -> NetworkXGraph:
        """The underlying ``networkx.DiGraph`` for direct algorithm access.

        Consumers may call any ``networkx`` function on this object
        (e.g. ``nx.pagerank(graph.digraph)``).

        Returns:
            The internal ``nx.DiGraph`` instance; not a copy.
        """
        return self._digraph

    def subgraph(
        self,
        feature: str | None = None,
    ) -> NetworkXGraph:
        """Return a networkx subgraph view, optionally scoped to
        *feature*.

        Args:
            feature: When set, restrict to nodes with this feature tag.

        Returns:
            ``nx.DiGraph`` (a subgraph view, not a copy).
        """
        if not feature:
            return self._digraph
        names = {n.name for n in self.get_feature_nodes(feature)}
        return self._digraph.subgraph(names)

    def ego_subgraph(
        self,
        node: str,
        depth: int = 1,
    ) -> NetworkXGraph:
        """Return the local (ego) subgraph around *node* up to *depth* hops.

        Mirrors Obsidian's local-graph view: the centre document plus every
        document reachable within *depth* link hops in either direction.  The
        traversal is undirected (a backlink is as relevant as a forward link
        for local context) via ``nx.ego_graph(..., undirected=True)``, but the
        returned graph is the directed subgraph induced on those nodes, so
        edge direction and the ``kind``/``multiplicity``/``weight`` attributes
        are preserved.

        Args:
            node: Centre node key.  Must exist in the graph.
            depth: Radius in hops (``>= 0``).  ``0`` returns just the centre
                node; ``1`` adds its immediate neighbours, and so on.

        Returns:
            A directed subgraph view of the canonical graph scoped to the ego
            neighbourhood.

        Raises:
            KeyError: If *node* is not a key in the graph.
            ValueError: If *depth* is negative.
        """
        if node not in self._digraph:
            raise KeyError(node)
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")
        ego = ego_graph(
            self._digraph,
            node,
            radius=depth,
            undirected=True,
        )
        # Induce the directed subgraph on the ego node set so edge direction
        # and edge attributes survive.
        return self._digraph.subgraph(ego.nodes())

    # -- Query methods -------------------------------------------------------

    def get_feature_rankings(
        self,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """Rank features by total incoming links to their documents.

        Args:
            limit: Maximum features to return.

        Returns:
            ``(feature_name, total_in_links)`` tuples descending.
        """
        scores: dict[str, int] = {}
        for node in self.nodes.values():
            if node.phantom:
                continue
            score = len(node.in_links)
            for tag in node.tags:
                if not DocType.from_tag(tag):
                    f_name = tag.lstrip("#")
                    scores[f_name] = scores.get(f_name, 0) + score
        return sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]

    def get_orphaned(self) -> list[str]:
        """Return document names that are truly isolated from the graph.

        A node is orphaned only when it has **no connections at all** --
        no incoming links, no outgoing links, and no sibling documents
        sharing the same feature tag.  Documents that link out to a plan
        or ADR (common for exec records) are connected and therefore not
        orphans.

        Returns:
            Sorted list of genuinely isolated node names
            (excludes ``readme``).
        """
        # Pre-compute which features have more than one document.
        # A node sharing a feature tag with at least one other node is
        # implicitly connected through that feature cluster.
        feature_sizes: dict[str, int] = {}
        for node in self.nodes.values():
            if node.feature:
                feature_sizes[node.feature] = feature_sizes.get(node.feature, 0) + 1

        return sorted(
            name
            for name, node in self.nodes.items()
            if not node.phantom
            and name.lower() != "readme"
            and not node.in_links
            and not node.out_links
            and (not node.feature or feature_sizes.get(node.feature, 0) <= 1)
        )

    def get_dangling_links(self) -> list[tuple[str, str]]:
        """Return all dangling link pairs recorded during graph construction.

        Returns:
            List of ``(source, target)`` tuples where *target* does not
            exist as a node in the graph.
        """
        return list(self._dangling_links)

    def get_feature_nodes(self, feature: str) -> list[DocNode]:
        """Return all nodes tagged with *feature*, sorted by date then name.

        Args:
            feature: Feature name (without ``#`` prefix).

        Returns:
            List of :class:`DocNode` instances sorted by ``(date, name)``.
        """
        tag = f"#{feature}" if not feature.startswith("#") else feature
        nodes = [n for n in self.nodes.values() if not n.phantom and tag in n.tags]
        return sorted(
            nodes,
            key=lambda n: (n.date or "", n.name),
        )

    def get_features(self) -> list[str]:
        """Return a sorted list of all feature names in the graph."""
        features: set[str] = set()
        for node in self.nodes.values():
            if not node.phantom and node.feature:
                features.add(node.feature)
        return sorted(features)

    def to_snapshot(self) -> VaultSnapshot:
        """Build a :data:`~vaultspec_core.vaultcore.checks._base.VaultSnapshot`
        from the graph's parsed node data.

        Each node's frontmatter tags, date, modified stamp, and related
        links are packed into a
        :class:`~vaultspec_core.vaultcore.models.DocumentMetadata`, paired with
        the node's body text, and keyed by filesystem path.

        Returns:
            Dict mapping each document's path to its ``(metadata, body)``
            tuple.
        """

        snapshot: VaultSnapshot = {}
        for node in self.nodes.values():
            # A working-tree snapshot is keyed by concrete filesystem paths.
            # Phantoms and ref-scoped nodes (which carry a virtual tree_path,
            # not a filesystem path) have ``path is None`` and are excluded so
            # the snapshot only ever describes real on-disk documents.
            if node.phantom or node.path is None:
                continue
            raw_related = node.frontmatter.get("related", [])
            related: list[str] = []
            if isinstance(raw_related, list):
                related_items = cast("list[Any]", raw_related)
                related = [str(r) for r in related_items if isinstance(r, str)]
            raw_superseded_by = node.frontmatter.get("superseded_by")
            superseded_by = (
                raw_superseded_by if isinstance(raw_superseded_by, str) else None
            )
            raw_step_id = node.frontmatter.get("step_id")
            step_id = raw_step_id if isinstance(raw_step_id, str) else None
            raw_body_schema = node.frontmatter.get("body_schema")
            body_schema = raw_body_schema if isinstance(raw_body_schema, str) else None
            raw_body_hash = node.frontmatter.get("body_hash")
            body_hash = raw_body_hash if isinstance(raw_body_hash, str) else None
            metadata = DocumentMetadata(
                tags=sorted(node.tags),
                date=node.date,
                modified=node.modified,
                related=related,
                superseded_by=superseded_by,
                step_id=step_id,
                body_schema=body_schema,
                body_hash=body_hash,
            )
            snapshot[node.path] = (metadata, node.body)
        return snapshot

    # -- Metrics (networkx algorithms) ---------------------------------------

    def counts(self, feature: str | None = None) -> GraphCounts:
        """Return the cheap descriptive counts for the graph or a feature.

        Produces exactly the ``total_nodes``, ``total_edges``, and
        ``total_features`` values :meth:`metrics` reports, without running
        any of the graph-theoretic analysis (centrality, components,
        density) that method bundles.  This is the surface render and
        orientation paths use; :meth:`metrics` is the explicit opt-in for
        analysis.

        Args:
            feature: When set, count only this feature's subgraph.

        Returns:
            A :class:`GraphCounts` instance.
        """
        if feature:
            g = self.subgraph(feature=feature)
            nodes: dict[str, DocNode] = {
                n.name: n for n in self.get_feature_nodes(feature)
            }
        else:
            g = self._digraph
            nodes = self.nodes
        phantom_count = 0
        features: set[str] = set()
        for node in nodes.values():
            if node.phantom:
                phantom_count += 1
            elif node.feature:
                features.add(node.feature)
        return GraphCounts(
            docs=g.number_of_nodes() - phantom_count,
            links=g.number_of_edges(),
            features=len(features),
        )

    def metrics(
        self,
        feature: str | None = None,
        *,
        _g: NetworkXGraph | None = None,
    ) -> GraphMetrics:
        """Compute aggregate statistics via graph-library algorithms.

        Delegates to ``nx.density``, ``nx.in_degree_centrality``,
        ``nx.number_weakly_connected_components``, and betweenness
        centrality through the C-backed engine seam
        (:func:`betweenness_centrality`, ``rustworkx`` with a networkx
        fallback) instead of manual computation.

        Args:
            feature: Compute metrics only for this feature's subgraph.
            _g: Pre-computed subgraph from :meth:`subgraph`. When
                supplied, the internal :meth:`subgraph` call is skipped
                so callers that already hold a reference (e.g.
                :meth:`to_dict`) avoid a redundant traversal and the
                expensive betweenness computation runs exactly once.
                This parameter is intentionally private (underscore
                prefix) and not part of the public API.

        Returns:
            A :class:`GraphMetrics` instance.
        """
        g = _g if _g is not None else self.subgraph(feature=feature)
        nodes = (
            {n.name: n for n in self.get_feature_nodes(feature)}
            if feature
            else self.nodes
        )

        n_nodes = g.number_of_nodes()
        n_edges = g.number_of_edges()

        # --- networkx degree analysis (exclude phantoms) ---
        max_in: tuple[str, int] = ("", 0)
        max_out: tuple[str, int] = ("", 0)
        if n_nodes:
            in_degs = {
                k: v
                for k, v in g.in_degree()
                if k not in self.nodes or not self.nodes[k].phantom
            }
            out_degs = {
                k: v
                for k, v in g.out_degree()
                if k not in self.nodes or not self.nodes[k].phantom
            }
            if in_degs:
                top = max(in_degs, key=lambda k: in_degs[k])
                max_in = (top, in_degs[top])
            if out_degs:
                top = max(out_degs, key=lambda k: out_degs[k])
                max_out = (top, out_degs[top])

        # --- networkx centrality algorithms ---
        in_cent: dict[str, float] = {}
        btwn_cent: dict[str, float] = {}
        if n_nodes > 1:
            in_cent = top_n(nx.in_degree_centrality(g))
            btwn_cent = top_n(betweenness_centrality(g))

        # --- feature / type counts (excludes phantoms) ---
        features: set[str] = set()
        by_type: dict[str, int] = {}
        by_feature: dict[str, int] = {}
        total_words = 0
        phantom_count = 0
        for node in nodes.values():
            if node.phantom:
                phantom_count += 1
                continue
            if node.feature:
                features.add(node.feature)
                by_feature[node.feature] = by_feature.get(node.feature, 0) + 1
            dt_key = node.doc_type.value if node.doc_type else "unknown"
            by_type[dt_key] = by_type.get(dt_key, 0) + 1
            total_words += node.word_count

        # --- networkx orphan / dangling ---
        orphan_count = len(self.get_orphaned())
        invalid_count = sum(
            1
            for src, tgt in self._dangling_links
            if src in nodes and tgt in self.nodes and self.nodes[tgt].phantom
        )

        # --- networkx connected components ---
        try:
            components = nx.number_weakly_connected_components(g)
        except nx.NetworkXError:
            components = 0

        return GraphMetrics(
            total_nodes=n_nodes - phantom_count,
            total_edges=n_edges,
            total_features=len(features),
            total_words=total_words,
            density=graph_density(g),
            avg_in_degree=(n_edges / n_nodes if n_nodes else 0.0),
            avg_out_degree=(n_edges / n_nodes if n_nodes else 0.0),
            max_in_degree=max_in,
            max_out_degree=max_out,
            in_degree_centrality=in_cent,
            betweenness_centrality=btwn_cent,
            phantom_count=phantom_count,
            orphan_count=orphan_count,
            dangling_link_count=invalid_count,
            connected_components=components,
            nodes_by_type=dict(sorted(by_type.items())),
            nodes_by_feature=dict(sorted(by_feature.items())),
        )

    # -- ASCII graph rendering (phart) ---------------------------------------

    def render_ascii(
        self,
        feature: str | None = None,
    ) -> str:
        """Render the graph as an ASCII diagram via ``phart``.

        Uses ``phart.ASCIIRenderer`` to produce a native directed-graph
        layout with box-drawn nodes and edge arrows  - the actual graph
        topology, not a hierarchical tree.

        Args:
            feature: When set, render only that feature's subgraph.

        Returns:
            Multi-line ASCII string of the graph layout.
        """
        return rendering.render_ascii(self, feature=feature)

    # -- Hierarchical tree rendering (box-free) --------------------------------

    def render_tree_lines(
        self,
        feature: str | None = None,
    ) -> list[TreeLine]:
        """Build a box-free :class:`~vaultspec_core.cli.rendering.TreeLine` list.

        Renders the vault as a hierarchical tree grouped by feature and
        doc-type, using the plain-text shape vocabulary.  This is
        complementary to :meth:`render_ascii` which shows the actual graph
        topology.

        Args:
            feature: Optional feature name to scope the tree.

        Returns:
            A list of :class:`~vaultspec_core.cli.rendering.TreeLine` objects
            ready for :func:`~vaultspec_core.cli.rendering.render_tree`.
        """
        return rendering.render_tree_lines(self, feature=feature)

    #: Maximum lines the tree render prints.  The title always carries the
    #: full corpus counts, the truncation is explicitly marked, and the
    #: ``--json`` envelope remains the uncapped machine contract, per the
    #: report-volume policy.
    TREE_RENDER_CAP = rendering.TREE_RENDER_CAP

    def render_tree(
        self,
        feature: str | None = None,
    ) -> None:
        """Print a box-free hierarchical tree to the console.

        Renders the vault grouped by feature and doc-type via the plain-text
        shape vocabulary.  This is complementary to :meth:`render_ascii` which
        shows the actual graph topology.  At most :attr:`TREE_RENDER_CAP`
        lines are printed; a marked truncation line reports the remainder and
        points at feature scoping or ``--json``.

        Args:
            feature: Optional feature name to scope the tree.
        """
        rendering.render_tree(self, feature=feature)

    # -- JSON serialisation (networkx node_link_data) ------------------------

    def _relativise_node_path(self, raw_path: Any) -> str | None:
        """Return *raw_path* as a vault-relative POSIX path, or ``None``.

        Args:
            raw_path: The ``path`` value off a serialised node dict.

        Returns:
            The vault-relative POSIX path string, or ``None``.
        """
        return api_export.relativise_node_path(self.root_dir, raw_path)

    def to_dict(
        self,
        feature: str | None = None,
        include_body: bool = False,
        *,
        node: str | None = None,
        depth: int = 1,
        include_derived: bool = True,
        derived_limit: int | None = None,
        derived_offset: int = 0,
    ) -> dict[str, Any]:
        """Return the graph as a JSON-serialisable dictionary.

        Uses ``networkx.readwrite.json_graph.node_link_data`` for the
        core node/edge structure, enriched with vault-specific metrics, the
        node-size hints carried on each node (``pagerank``, ``in_degree``),
        the explicit-edge attributes carried on each edge (``kind``,
        ``multiplicity``, ``weight``), and a parallel ``derived_edges`` array
        of implicit relatedness edges that is never mixed into the canonical
        ``edges`` array.

        Scoping precedence: when *node* is given the export is the ego
        subgraph around it at *depth* hops; otherwise *feature* scopes to a
        single feature; otherwise the full graph is exported.

        Args:
            feature: When set (and *node* is unset), export only that
                feature's subgraph.
            include_body: Include the full markdown body text in each
                node.  Defaults to ``False`` to keep output compact.
            node: When set, export the ego subgraph around this node key.
            depth: Ego-graph radius in hops; only used when *node* is set.
            include_derived: When ``True`` (default), emit the
                ``derived_edges`` array; when ``False`` emit an empty one.

        Returns:
            Dictionary with ``directed``, ``multigraph``, ``graph``,
            ``nodes``, ``edges``, ``derived_edges``, ``root``, ``ref``,
            ``feature``, and ``metrics`` keys. ``ref`` names the git ref for a
            ref-scoped build (issue #160) and is ``None`` for a working-tree
            build.
        """
        return api_export.to_dict(
            self,
            feature=feature,
            include_body=include_body,
            node=node,
            depth=depth,
            include_derived=include_derived,
            derived_limit=derived_limit,
            derived_offset=derived_offset,
        )

    def to_json(
        self,
        feature: str | None = None,
        include_body: bool = False,
        indent: int = 2,
    ) -> str:
        """Serialise the graph to a JSON string.

        Args:
            feature: Scope to a single feature.
            include_body: Include full markdown body in output.
            indent: JSON indentation level.

        Returns:
            JSON string.
        """
        return api_export.to_json(
            self,
            feature=feature,
            include_body=include_body,
            indent=indent,
        )
