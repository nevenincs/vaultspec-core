"""Construction passes for the vault document graph.

Sibling of :mod:`vaultspec_core.graph.api` (which owns
:class:`~vaultspec_core.graph.api.VaultGraph` itself),
:mod:`vaultspec_core.graph.api_export` (the wire format), and
:mod:`vaultspec_core.graph.rendering` (the ASCII and tree views). This module
owns how a graph is populated: the ingress read, the cache round-trip, the
working-tree and ref-scoped rebuilds, and the shared assembly passes that turn
parsed documents into nodes and edges.

The public surface stays on
:class:`~vaultspec_core.graph.api.VaultGraph` - construct a graph, or call
``graph.ensure_raw_texts()``, rather than these functions directly. The cache
policy itself (when to load, when to rewrite) stays on
:class:`~vaultspec_core.graph.api.VaultGraph`; this module supplies the passes
that policy drives.
"""

from __future__ import annotations

import logging
import pathlib
from collections import Counter
from typing import TYPE_CHECKING, Any

import networkx as nx

from ..vaultcore import (
    extract_related_links,
    extract_wiki_links,
    get_doc_type,
    parse_frontmatter,
    parse_vault_metadata,
)
from .algorithms import (
    PAGERANK_ALPHA,
    docnode_from_attrs,
    edge_kind,
    extract_feature,
    extract_title,
    pagerank,
)
from .models import DocNode, EncodingIssue
from .networkx_runtime import node_link_data, node_link_graph

if TYPE_CHECKING:
    from . import cache
    from .api import VaultGraph

logger = logging.getLogger(__name__)


__all__ = [
    "assemble_from_by_stem",
    "ensure_raw_texts",
    "ingest_document",
    "is_archived",
    "load_from_cache",
    "populate_node_from_content",
    "rebuild_from_corpus",
    "rebuild_from_files",
    "resolve_link",
    "to_cache_graph",
]


def to_cache_graph(graph: VaultGraph) -> dict[str, Any]:
    """Return the node-link serialisation of the canonical graph for caching.

    Uses the same ``edges="edges"`` node-link contract the JSON export
    uses, then injects each node's body text (which is held on the
    :class:`~vaultspec_core.graph.models.DocNode`, not on the networkx
    node) so a cache load can reconstruct a behaviourally identical graph,
    including ``to_dict`` with ``include_body=True``.

    Args:
        graph: The graph to serialise.

    Returns:
        A node-link ``dict`` with body text attached to each node.
    """
    data = node_link_data(graph._digraph)
    for node_dict in data.get("nodes", []):
        nid = node_dict.get("id", "")
        doc = graph.nodes.get(nid)
        node_dict["body"] = doc.body if doc is not None else ""
    return data


def load_from_cache(graph: VaultGraph, payload: cache.GraphCachePayload) -> None:
    """Reconstruct the graph state from a validated cache payload.

    Rebuilds the digraph, node map, stem index, and dangling-link list from
    the serialised node-link data so the loaded graph is behaviourally
    identical to a fresh build (same nodes, edges, attributes, and
    node-size metrics). No filesystem parsing occurs.

    Args:
        graph: The graph to populate.
        payload: A cache payload that has already passed
            :func:`vaultspec_core.graph.cache.validate`.
    """
    graph._digraph = node_link_graph(payload.graph)
    graph.nodes = {}
    graph._stem_index = {}
    by_stem: dict[str, list[str]] = {}
    for key in graph._digraph.nodes():
        attrs = graph._digraph.nodes[key]
        graph.nodes[key] = docnode_from_attrs(key, attrs)
        # The node body is held on the DocNode, not the nx node; pull it
        # back off the cached node attrs and drop it so the nx node
        # attribute set matches a fresh build exactly.
        body = attrs.pop("body", "")
        graph.nodes[key].body = body
        # Phantoms are excluded from the stem index to match fresh-build
        # semantics: rebuild_from_files only indexes real (non-phantom)
        # nodes in passes 1a/1b; phantoms are added later in pass 2 and
        # never entered into the stem index.
        if not attrs.get("phantom", False):
            bare_stem = key.split("/", 1)[1] if "/" in key else key
            by_stem.setdefault(bare_stem, []).append(key)
    for bare_stem, keys in by_stem.items():
        graph._stem_index[bare_stem] = sorted(keys)
    graph._dangling_links = [(pair[0], pair[1]) for pair in payload.dangling_links]
    # A document that failed to read or decode never becomes a usable node,
    # so the cache carries these separately; restoring them keeps a warm
    # run's encoding findings identical to a cold one's.
    graph._encoding_issues = [
        EncodingIssue(pathlib.Path(raw_path), kind, detail, start)
        for raw_path, kind, detail, start in payload.encoding_issues
    ]
    logger.info(
        "Graph loaded from cache: %d nodes, %d edges",
        graph._digraph.number_of_nodes(),
        graph._digraph.number_of_edges(),
    )


def rebuild_from_files(graph: VaultGraph, scanned_files: list[pathlib.Path]) -> None:
    """Rebuild the graph by parsing every scanned file.

    Uses a two-pass strategy:

    1. **Pass 1** - create :class:`~vaultspec_core.graph.models.DocNode`
       instances, detecting stem collisions. When two files share the same
       stem (e.g. ``adr/my-doc.md`` and ``reference/my-doc.md``), all
       colliding nodes are re-keyed as ``type/stem`` so that no data is
       silently dropped.
    2. **Pass 2** - extract links and create directed edges. Bare
       wiki-link stems that match multiple qualified keys fan-out to
       all variants (with a logged warning).

    Args:
        graph: The graph to populate.
        scanned_files: The vault document paths to parse, as returned by
            ``scan_vault``.
    """
    graph.nodes = {}
    graph._digraph = nx.DiGraph()
    graph._dangling_links = []
    graph._raw_texts = {}
    graph._encoding_issues = []

    # Pass 1a: collect all DocNodes keyed by stem, detecting collisions
    by_stem: dict[str, list[DocNode]] = {}

    for path in scanned_files:
        logger.debug("Graph pass 1: reading %s", path)
        stem = path.stem
        doc_type = get_doc_type(path, graph.root_dir)

        node = DocNode(path=path, name=stem, doc_type=doc_type)

        content = ingest_document(graph, path)
        if content is not None:
            populate_node_from_content(node, content)

        by_stem.setdefault(stem, []).append(node)

    assemble_from_by_stem(graph, by_stem)


def ingest_document(graph: VaultGraph, path: pathlib.Path) -> str | None:
    """Read *path* once, recording its raw text and any encoding issue.

    The single ingress read: the file's bytes are read exactly once,
    decoded as UTF-8, and newline-normalised the way ``read_text``'s
    universal-newline mode would (``\\r\\n`` and ``\\r`` become ``\\n``)
    so the parse consumes identical input to the previous per-consumer
    reads. The normalised text and the source's CRLF convention are
    retained in ``graph.raw_texts`` for content-consuming checks, and a
    read or decode failure is recorded in ``graph.encoding_issues``
    instead of being silently dropped.

    Args:
        graph: The graph recording the read.
        path: The document to read.

    Returns:
        The normalised document text, or ``None`` when the file could
        not be read or decoded.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError as e:
        graph._encoding_issues.append(EncodingIssue(path, "read", str(e), None))
        logger.warning("Failed to read metadata from %s: %s", path, e)
        return None
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        graph._encoding_issues.append(EncodingIssue(path, "decode", e.reason, e.start))
        logger.warning("Failed to read metadata from %s: %s", path, e)
        return None
    crlf = "\r\n" in decoded
    content = decoded.replace("\r\n", "\n").replace("\r", "\n")
    graph._raw_texts[path] = (content, crlf)
    return content


def ensure_raw_texts(graph: VaultGraph) -> None:
    """Guarantee ``graph.raw_texts`` is populated for a working-tree graph.

    A cold build fills the raw-text map during its parse; a cache-hit
    build parses nothing, so a caller that needs document text (the
    check pipeline) invokes this to perform the run's single ingress
    read pass. A no-op when the map is already populated or when the
    graph is ref-scoped (checks do not run against history).

    Args:
        graph: The graph whose raw-text map is being guaranteed.
    """
    if graph._raw_texts or graph.ref is not None:
        return
    from ..vaultcore.scanner import scan_vault

    graph._encoding_issues = []
    for path in scan_vault(graph.root_dir, run_migrations=False):
        ingest_document(graph, path)


def rebuild_from_corpus(
    graph: VaultGraph, corpus: list[tuple[str, str]], docs_dir_name: str
) -> None:
    """Rebuild the graph from in-memory ``(tree_path, content)`` pairs.

    The ref-scoped build path (issue #160): instead of walking the working
    tree, the corpus is read from the git object database by
    :func:`vaultspec_core.graph.refscan.read_vault_at_ref`. Each pair
    carries a virtual tree path (e.g. ``.vault/adr/foo.md``) and the blob's
    UTF-8 text. Document-type classification reads the tree path via
    :func:`vaultspec_core.vaultcore.scanner.get_doc_type_from_tree_path`,
    and the node ``path`` is the virtual tree path. After Pass 1a the build
    is identical to the working-tree path, so the graph is structurally the
    same as a checkout-based build of the same corpus.

    Args:
        graph: The graph to populate.
        corpus: ``(tree_path, content)`` pairs for the ref's vault docs.
        docs_dir_name: The configured docs directory name (e.g. ``.vault``).
    """
    from ..vaultcore.scanner import get_doc_type_from_tree_path

    graph.nodes = {}
    graph._digraph = nx.DiGraph()
    graph._dangling_links = []

    by_stem: dict[str, list[DocNode]] = {}
    for tree_path, content in corpus:
        stem = pathlib.PurePosixPath(tree_path).stem
        doc_type = get_doc_type_from_tree_path(tree_path, docs_dir_name)
        node = DocNode(path=None, name=stem, doc_type=doc_type, tree_path=tree_path)
        try:
            populate_node_from_content(node, content)
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse blob %s: %s", tree_path, e)
        by_stem.setdefault(stem, []).append(node)

    assemble_from_by_stem(graph, by_stem)


def populate_node_from_content(node: DocNode, content: str) -> None:
    """Parse a document's *content* and populate *node*'s metadata fields.

    Shared by the working-tree and ref-scoped build paths so both derive
    tags, dates, feature, frontmatter, body, word count, and title from
    the same content-bound parsers (which never touch the filesystem).
    """
    metadata, body = parse_vault_metadata(content)
    raw_fm, _ = parse_frontmatter(content)

    node.tags = set(metadata.tags)
    node.date = metadata.date
    node.modified = metadata.modified
    node.feature = extract_feature(node.tags)
    node.frontmatter = raw_fm
    node.body = body
    node.word_count = len(body.split())
    node.title = extract_title(body)


def assemble_from_by_stem(graph: VaultGraph, by_stem: dict[str, list[DocNode]]) -> None:
    """Run the shared graph-assembly passes over the collected nodes.

    Passes 1b through 4 (key assignment / collision qualification, edge
    extraction, in/out-link sync, and node-size hints) are identical for
    the working-tree and ref-scoped build paths, which differ only in how
    Pass 1a's ``by_stem`` map is produced.

    Args:
        graph: The graph to populate.
        by_stem: Map of bare stem to the
            :class:`~vaultspec_core.graph.models.DocNode` instances that
            share it, as produced by the Pass-1a collectors.
    """
    # Pass 1b: assign unique keys  - qualify colliding stems with
    # their doc-type prefix, build a stem-to-keys index for link
    # resolution in pass 2.
    graph._stem_index = {}

    for stem, node_list in by_stem.items():
        if len(node_list) == 1:
            # Unique stem  - use it directly as the key.
            node = node_list[0]
            graph.nodes[stem] = node
            graph._digraph.add_node(stem, **node.to_nx_attrs())
            graph._stem_index[stem] = [stem]
        else:
            # Collision  - qualify each with its doc-type directory.
            keys: list[str] = []
            for node in node_list:
                dt = node.doc_type.value if node.doc_type else "unknown"
                qualified = f"{dt}/{stem}"
                node.name = qualified
                graph.nodes[qualified] = node
                graph._digraph.add_node(
                    qualified,
                    **node.to_nx_attrs(),
                )
                keys.append(qualified)
            # Sort so the index is deterministic across platforms and
            # matches the cache-rebuild path (which also sorts); raw scan
            # order is filesystem-dependent and diverges on Linux vs
            # Windows, breaking cached-vs-fresh parity.
            graph._stem_index[stem] = sorted(keys)
            logger.warning(
                "Stem collision for '%s': qualified as %s",
                stem,
                sorted(keys),
            )

    logger.info(
        "Graph pass 1: created %d nodes (%d stem collisions)",
        len(graph.nodes),
        sum(1 for v in graph._stem_index.values() if len(v) > 1),
    )

    # Pass 2: extract links -> edges.  Unresolved targets become
    # phantom nodes so the graph mirrors Obsidian's "not created"
    # link model.  Iterate over a snapshot of the real-node keys
    # because the dict grows as phantoms are added.
    real_node_keys = list(graph.nodes.keys())
    for name in real_node_keys:
        node = graph.nodes[name]
        try:
            # Keep the body and related extractions separate so each
            # resolved edge can record its provenance (body wiki-link,
            # related frontmatter, or both).  Both extractors now return
            # a Counter, preserving per-target multiplicity.
            body_links = extract_wiki_links(node.body)
            related_links = extract_related_links(
                node.frontmatter.get("related", []),
            )

            # Resolve each raw target to one or more node keys, summing
            # the source multiplicity onto every resolved key and unioning
            # the provenance kinds.  Iterating a Counter yields its keys.
            target_counts: Counter[str] = Counter()
            target_kinds: dict[str, set[str]] = {}
            for raw_target, count in body_links.items():
                for resolved_key in resolve_link(graph, raw_target):
                    target_counts[resolved_key] += count
                    target_kinds.setdefault(resolved_key, set()).add("body")
            for raw_target, count in related_links.items():
                for resolved_key in resolve_link(graph, raw_target):
                    target_counts[resolved_key] += count
                    target_kinds.setdefault(resolved_key, set()).add("related")

            node.out_links = set(target_counts)

            for target_key, multiplicity in target_counts.items():
                kind = edge_kind(target_kinds[target_key])
                if target_key in graph.nodes:
                    graph.nodes[target_key].in_links.add(name)
                    graph._digraph.add_edge(
                        name,
                        target_key,
                        kind=kind,
                        multiplicity=multiplicity,
                    )
                    if graph.nodes[target_key].phantom and not is_archived(
                        graph, target_key
                    ):
                        graph._dangling_links.append(
                            (name, target_key),
                        )
                else:
                    # Create a phantom node (deduplicated).
                    phantom = DocNode(
                        path=None,
                        name=target_key,
                        phantom=True,
                    )
                    graph.nodes[target_key] = phantom
                    graph._digraph.add_node(
                        target_key,
                        **phantom.to_nx_attrs(),
                    )
                    phantom.in_links.add(name)
                    graph._digraph.add_edge(
                        name,
                        target_key,
                        kind=kind,
                        multiplicity=multiplicity,
                    )
                    if not is_archived(graph, target_key):
                        graph._dangling_links.append(
                            (name, target_key),
                        )
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(
                "Failed to extract links from %s: %s",
                node.path,
                e,
            )

    # Pass 2b: normalise edge weight against the maximum multiplicity in
    # the graph so the strongest explicit edge has weight 1.0 and every
    # other edge is its multiplicity as a fraction of that maximum.  The
    # scheme is linear, deterministic, and exactly testable:
    #   weight = multiplicity / max_multiplicity_in_graph
    # When the graph has no edges there is nothing to normalise.
    multiplicities = [
        data["multiplicity"] for _, _, data in graph._digraph.edges(data=True)
    ]
    max_multiplicity = max(multiplicities) if multiplicities else 0
    for _src, _tgt, data in graph._digraph.edges(data=True):
        data["weight"] = (
            data["multiplicity"] / max_multiplicity if max_multiplicity else 0.0
        )

    # Pass 3: sync nx node attrs with updated in_links/out_links
    for name, node in graph.nodes.items():
        graph._digraph.nodes[name]["out_links"] = sorted(
            node.out_links,
        )
        graph._digraph.nodes[name]["in_links"] = sorted(
            node.in_links,
        )

    # Pass 4: node-size hints.  Attach pagerank and raw in-degree so a GUI
    # consumer can size nodes without recomputing.  PageRank uses the
    # pure-Python power iteration in pagerank with a fixed damping factor
    # (PAGERANK_ALPHA) and a uniform initial vector, so the result is
    # deterministic for a fixed graph and exactly testable.  An empty
    # graph yields no scores.
    if graph._digraph.number_of_nodes():
        pagerank_scores = pagerank(graph._digraph, alpha=PAGERANK_ALPHA)
    else:
        pagerank_scores = {}
    in_degree = dict(graph._digraph.in_degree())
    for name in graph._digraph.nodes():
        graph._digraph.nodes[name]["pagerank"] = pagerank_scores.get(name, 0.0)
        graph._digraph.nodes[name]["in_degree"] = in_degree.get(name, 0)

    logger.info(
        "Graph build complete: %d nodes, %d edges",
        graph._digraph.number_of_nodes(),
        graph._digraph.number_of_edges(),
    )


def is_archived(graph: VaultGraph, target: str) -> bool:
    """Check if target exists under .vault/_archive/."""
    from ..config import get_config

    cfg = get_config()
    archive_dir = graph.root_dir / cfg.docs_dir / "_archive"
    if not archive_dir.exists():
        return False
    target_norm = target.replace("\\", "/")
    if "/" in target_norm:
        return (archive_dir / f"{target_norm}.md").exists()
    else:
        return len(list(archive_dir.rglob(f"{target_norm}.md"))) > 0


def resolve_link(graph: VaultGraph, target: str) -> list[str]:
    """Resolve a wiki-link target to one or more node keys.

    Resolution order:

    1. Exact match against an existing node key (handles both bare
       stems and already-qualified ``type/stem`` references).
    2. Stem index lookup  - if the bare stem maps to multiple
       qualified keys, all are returned and a warning is logged.
    3. Match in .vault/_archive/ - returns the resolved archived key
       so it can be resolved without being flagged as dangling.
    4. No match  - returns the original target so it is recorded as
       a dangling link.
    """
    # Exact key match (unique stem or qualified reference)
    if target in graph.nodes:
        return [target]

    # Stem index lookup (handles collisions)
    keys = graph._stem_index.get(target, [])
    if keys:
        if len(keys) > 1:
            logger.debug(
                "Ambiguous wiki-link [[%s]] resolved to %d nodes: %s",
                target,
                len(keys),
                keys,
            )
        return keys

    # Try to resolve against .vault/_archive/
    from ..config import get_config

    cfg = get_config()
    archive_dir = graph.root_dir / cfg.docs_dir / "_archive"
    if archive_dir.exists():
        target_norm = target.replace("\\", "/")
        if "/" in target_norm:
            if (archive_dir / f"{target_norm}.md").exists():
                return [target_norm]
        else:
            matches = list(archive_dir.rglob(f"{target_norm}.md"))
            if matches:
                resolved: list[str] = []
                for match in matches:
                    rel = match.relative_to(archive_dir)
                    key = str(rel.with_suffix("")).replace("\\", "/")
                    resolved.append(key)
                return resolved

    # No match  - treat as dangling link
    return [target]
