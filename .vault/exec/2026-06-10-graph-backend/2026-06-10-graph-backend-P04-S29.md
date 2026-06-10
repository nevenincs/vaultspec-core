---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S29
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# wire cache loading into graph construction with any fingerprint mismatch falling back to full rebuild

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Added a use-cache flag to the graph constructor, defaulting to on because cache
  validation is exact and a corrupt cache degrades silently to a rebuild.
- Split the monolithic build into a scan-once pass, a cache-load branch, and a
  rebuild-from-files branch; the build scans the vault once, fingerprints the scanned
  file set, and consults the cache before any parse.
- Loaded the serialised graph and skipped re-parsing on a validated cache hit;
  reconstructed the digraph, node map, stem index, and dangling links from the cached
  node-link data so the loaded object is behaviourally identical to a fresh build.
- Fell back to a full rebuild on any miss (changed, added, or removed file, an absent
  cache, or a corrupt cache) and rewrote the cache after the rebuild.
- Persisted each node's body text into the cached node-link data and stripped it back
  off the networkx node on load, so the cached object reconstructs body-bearing JSON
  exports without retaining body on the graph node.
- Added a pure inverse of the node attribute serialiser to rebuild a document node
  from cached attributes.

## Outcome

The cache is wired transparently and always-on by default. A probe over a synthetic
corpus with stem collisions, phantoms, and dangling links confirmed the second build is
a cache hit whose body-bearing JSON export is byte-identical to the first build, that
node, edge, and dangling-link counts match, and that a forced no-cache build is also
identical. All 117 existing graph tests pass; lint and type checks are clean.

## Notes

The reconstruction is sound because the canonical graph carries every attribute a query
needs on its nodes and edges, and the cache stores the exact node-link contract the JSON
export uses. The only in-memory difference a cache load can introduce is that frontmatter
date values parsed from unquoted YAML arrive as strings rather than date objects, because
the JSON store coerces them; this is invisible at every public surface, because the JSON
export already coerces the same values through its string default. The stem index is
rebuilt from node keys rather than persisted, since it is consulted only during link
resolution on the rebuild path and never after a cache load.
