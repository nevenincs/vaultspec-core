---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S01
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# pass an explicit edges keyword to the node-link serialisation call so the wire key is version-independent

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Passed `edges="edges"` explicitly to `json_graph.node_link_data(g)` in `VaultGraph.to_dict` in `src/vaultspec_core/graph/api.py`.
- Added inline comment explaining the networkx version dependency (default changed from "links" in \<=3.5 to "edges" in >=3.6).

## Outcome

The wire key for the node-link JSON serialisation is now deterministic regardless of which networkx version resolves. All 58 existing graph tests pass.

## Notes

No incidents. The change is a one-line addition of a keyword argument.
