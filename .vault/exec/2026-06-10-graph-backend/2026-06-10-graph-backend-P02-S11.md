---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S11
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# create the derived relatedness edge module computing reciprocity, shared-tag, jaccard, adamic-adar, and co-citation signals with documented composition coefficients

## Scope

- `src/vaultspec_core/graph/derived.py`

## Description

- Create the derived relatedness module as pure, deterministic functions over
  a vault graph that never mutate the canonical DiGraph.
- Declare the six version-pinned composition coefficients as named module
  constants plus a coefficients version integer, documenting the linear blend
  in a header comment.
- Implement the `DerivedEdge` dataclass carrying sorted endpoints, a dominant
  `kind` label, a raw per-signal `signals` map, and the composed `weight`,
  with a JSON-serialisable `to_dict`.
- Compute reciprocity (both directed edges present), shared-feature (same
  feature tag), shared-tag (count of shared semantic tags, excluding directory
  tags and the feature tag), Jaccard and Adamic-Adar via the networkx
  link-prediction family on an undirected real-node projection, and
  co-citation (count of common predecessors) over the directed graph.
- Emit one derived edge per unordered real-document pair that fires at least
  one signal, sorted by descending composed weight then endpoints for a
  deterministic order.

## Outcome

The module produces a parallel, on-demand relatedness edge set with explicit
per-signal provenance and an exactly-recomputable composed weight, computed
without touching the checker-facing canonical graph. A probe over the 120-doc
synthetic corpus produced a stable 1828-edge set across repeated calls with
identical ordering; the composed weight of the top edge recomputed bit-for-bit
from its raw signals. ruff and ty report clean.

## Notes

Directory tags are excluded from the shared-tag signal because every document
carries exactly one and sharing it would connect the entire corpus; the
feature tag is excluded there too because shared-feature handles it. The
Adamic-Adar coefficient is deliberately the smallest because its raw score is
unbounded above, so the blend is a ranking aid rather than a probability. The
module is not yet re-exported from the graph package; the payload-emission
step imports it directly.
