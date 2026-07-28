"""Data models for the vault document relationship graph.

Carries the plain-data shapes :mod:`vaultspec_core.graph.api` builds and
serialises: :class:`DocNode` (one graph node per document),
:class:`GraphMetrics` (opt-in aggregate statistics), :class:`EncodingIssue`
(a document the ingress read could not read or decode), and
:class:`GraphCounts` (cheap descriptive counts for render/orientation paths).
None of these types touch the filesystem or ``networkx`` directly; they are
populated and consumed by :class:`~vaultspec_core.graph.api.VaultGraph`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathlib

    from ..vaultcore import DocType

__all__ = ["DocNode", "EncodingIssue", "GraphCounts", "GraphMetrics"]


@dataclass
class DocNode:
    """A node in the vault document graph representing a single document.

    Carries the full parsed frontmatter, body text, and derived connection
    metadata so that consumers never need to re-read the filesystem.

    Attributes:
        path: Filesystem path to the document file, or ``None`` for phantoms
            and for ref-scoped nodes (which have no working-tree path; their
            virtual location is carried by ``tree_path`` instead).
        tree_path: For a ref-scoped node (issue #160), the repo-relative POSIX
            tree path of the blob (e.g. ``.vault/adr/foo.md``); ``None`` for a
            working-tree node, whose location is ``path``. Serialised as the
            node's ``path`` attribute so a consumer sees one ``path`` field
            regardless of build source.
        name: Document stem (filename without extension), used as graph key.
        doc_type: Categorised document type from vault folder location.
        feature: Feature tag (without ``#`` prefix), or ``None``.
        date: ISO-8601 date string from frontmatter, or ``None``.
        modified: CLI-maintained ``modified:`` recency stamp as parsed
            from frontmatter, or ``None`` when the field is absent. Carried
            verbatim (not canonicalised) so the modified-stamp checker can
            still distinguish a non-canonical value from a missing one.
        title: First ``# heading`` extracted from body, or ``None``.
        tags: Set of all frontmatter tags.
        frontmatter: Raw frontmatter dict (everything parsed from YAML).
        body: Markdown body text after the YAML fence.
        word_count: Approximate word count of the body.
        out_links: Names of documents this document links to.
        in_links: Names of documents that link to this document.
        phantom: ``True`` for unresolved wiki-link targets that have no
            backing file.  Mirrors Obsidian's "not created" node concept.
    """

    path: pathlib.Path | None
    name: str
    doc_type: DocType | None = None
    tree_path: str | None = None
    feature: str | None = None
    date: str | None = None
    modified: str | None = None
    title: str | None = None
    tags: set[str] = field(default_factory=set)
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    word_count: int = 0
    out_links: set[str] = field(default_factory=set)
    in_links: set[str] = field(default_factory=set)
    phantom: bool = False

    def to_nx_attrs(self) -> dict[str, Any]:
        """Return a networkx-compatible node attribute dict.

        Converts non-serialisable types (sets, Path, enums) to plain
        JSON-friendly values suitable for storage on a ``nx.DiGraph``
        node and for ``nx.node_link_data`` serialisation.

        Returns:
            Dict with string-valued ``path``, sorted lists for ``tags``,
            ``out_links``, and ``in_links``, and ``None``-safe scalar fields.
        """
        return {
            "name": self.name,
            # A ref-scoped node carries its virtual tree path; a working-tree
            # node carries the stringified filesystem path. Either way the
            # serialised attribute is a single ``path`` field.
            "path": (
                self.tree_path
                if self.tree_path is not None
                else (str(self.path) if self.path else None)
            ),
            "doc_type": (self.doc_type.value if self.doc_type else None),
            "feature": self.feature,
            "date": self.date,
            "modified": self.modified,
            "title": self.title,
            "tags": sorted(self.tags),
            "frontmatter": self.frontmatter,
            "word_count": self.word_count,
            "out_links": sorted(self.out_links),
            "in_links": sorted(self.in_links),
            "phantom": self.phantom,
        }


@dataclass
class GraphMetrics:
    """Aggregate statistics describing the shape and size of a vault graph.

    All graph-theoretic values (density, centrality, components) are
    computed by ``networkx`` built-in algorithms rather than manual
    calculation.

    Attributes:
        total_nodes: Number of documents in the graph.
        total_edges: Number of directed link edges.
        total_features: Number of distinct feature tags.
        total_words: Sum of word counts across all documents.
        density: Graph density (0.0 to 1.0) via ``nx.density``.
        avg_in_degree: Mean incoming edges per node.
        avg_out_degree: Mean outgoing edges per node.
        max_in_degree: Highest incoming edge count (with node name).
        max_out_degree: Highest outgoing edge count (with node name).
        in_degree_centrality: ``nx.in_degree_centrality`` scores.
        betweenness_centrality: ``nx.betweenness_centrality`` scores.
        phantom_count: Number of phantom (unresolved) nodes in the graph.
        orphan_count: Truly isolated nodes (no links and no feature siblings).
        dangling_link_count: Edges pointing to phantom (unresolved) targets.
        connected_components: Weakly connected components via networkx.
        nodes_by_type: Document count per ``DocType``.
        nodes_by_feature: Document count per feature tag.
    """

    total_nodes: int = 0
    total_edges: int = 0
    total_features: int = 0
    total_words: int = 0
    density: float = 0.0
    avg_in_degree: float = 0.0
    avg_out_degree: float = 0.0
    max_in_degree: tuple[str, int] = ("", 0)
    max_out_degree: tuple[str, int] = ("", 0)
    in_degree_centrality: dict[str, float] = field(
        default_factory=dict,
    )
    betweenness_centrality: dict[str, float] = field(
        default_factory=dict,
    )
    phantom_count: int = 0
    orphan_count: int = 0
    dangling_link_count: int = 0
    connected_components: int = 0
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    nodes_by_feature: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary of all metrics.

        Converts ``max_in_degree`` and ``max_out_degree`` tuples to
        ``{"node": str, "count": int}`` dicts for clean JSON output.

        Returns:
            Flat dict of all metric fields; safe to pass to ``json.dumps``.
        """
        d = asdict(self)
        d["max_in_degree"] = {
            "node": self.max_in_degree[0],
            "count": self.max_in_degree[1],
        }
        d["max_out_degree"] = {
            "node": self.max_out_degree[0],
            "count": self.max_out_degree[1],
        }
        return d


@dataclass(frozen=True)
class EncodingIssue:
    """A document the ingress read could not read or decode.

    Attributes:
        path: Absolute path of the affected file.
        kind: ``"read"`` for an :class:`OSError`, ``"decode"`` for a
            :class:`UnicodeDecodeError`.
        detail: The error string (``read``) or decode failure reason
            (``decode``).
        start: The failing byte offset for ``decode`` issues, else ``None``.
    """

    path: pathlib.Path
    kind: str
    detail: str
    start: int | None


@dataclass(frozen=True)
class GraphCounts:
    """Cheap descriptive counts of a vault graph.

    The always-affordable half of the metrics surface: document, link, and
    feature counts derived from the graph structure alone, with no
    graph-theoretic algorithm behind them.  Render and orientation paths
    consume this class; the expensive analysis in
    :meth:`~vaultspec_core.graph.api.VaultGraph.metrics` (centrality,
    components, density) is opt-in and never bought implicitly by a display
    path.

    Attributes:
        docs: Number of real (non-phantom) documents in scope.
        links: Number of directed link edges in scope.
        features: Number of distinct feature tags in scope.
    """

    docs: int
    links: int
    features: int
