---
tags:
  - '#plan'
  - '#graph-hardening'
date: '2026-03-22'
modified: '2026-07-31'
body_hash: 'sha256:8587d8b4737bb8178ff922e2f4911940d94634cd755ac263647c701f76b7c3c3'
tier: L2
related:
  - '[[2026-03-22-graph-hardening-adr]]'
  - '[[2026-03-22-graph-hardening-research]]'
---

# `graph-hardening` plan

## Steps

### Phase `P01` - phantom nodes in the graph

create phantom DocNodes for unresolved wiki-link targets so dangling links become first-class graph state

- [x] `P01.S01` - add the phantom DocNode field and create deduplicated phantom nodes for unresolved link targets during graph build; `src/vaultspec_core/graph/api.py`.

### Phase `P02` - guards and metrics

keep phantom nodes out of orphan detection and snapshots and surface phantom and invalid-link counts in GraphMetrics

- [x] `P02.S02` - exclude phantom nodes from get_orphaned and to_snapshot, and add phantom_count and invalid_link_count to GraphMetrics; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S03` - skip phantom nodes when check_schema and check_references compute linked types and the feature type index; `src/vaultspec_core/vaultcore/checks/references.py`.

### Phase `P03` - rendering

render phantom targets distinctly in the tree view, JSON export, and metrics output

- [x] `P03.S04` - render phantom targets as not created in the tree view and JSON export and show phantom count in CLI metrics output; `src/vaultspec_core/graph/rendering.py`.

### Phase `P04` - check_dangling checker

add an ERROR-severity checker that reports and can fix dangling wiki-links

- [x] `P04.S05` - add check_dangling reporting ERROR diagnostics for unresolved links, with fix support and CLI wiring; `src/vaultspec_core/vaultcore/checks/dangling.py`.

### Phase `P05` - pre-commit hook wiring

block commits that introduce dangling wiki-links

- [ ] `P05.S06` - add a read-only pre-commit hook that blocks commits containing dangling wiki-links; `.pre-commit-config.yaml`.

### Phase `P06` - tests

cover phantom node creation, guards, metrics, rendering, and the dangling checker

- [x] `P06.S07` - cover phantom node creation, guards, metrics, rendering, and the dangling checker with tests; `src/vaultspec_core/graph/tests/test_graph.py`.
