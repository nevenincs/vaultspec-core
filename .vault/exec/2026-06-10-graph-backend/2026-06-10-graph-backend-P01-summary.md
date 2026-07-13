---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# `graph-backend` `P01` summary

Phase `P01` pinned the graph JSON wire contract so every downstream consumer inherits a
stable, versioned envelope. The node-link edge key is now version-independent, the
networkx floor is raised to the version where that key became the default, the wasteful
double metrics pass on the JSON path is gone, the envelope is bumped to schema version 2
behind a backward-compatible helper change, and a freeze test plus the previously
missing branch tests close the known coverage gaps. The phase passed code review with no
critical or high findings.

- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/cli/rendering.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/graph/tests/test_graph.py`
- Modified: `src/vaultspec_core/graph/tests/conftest.py`
- Modified: `pyproject.toml`
- Modified: `uv.lock`
- Created: `src/vaultspec_core/graph/tests/test_contract.py`

## Description

`S01` passed an explicit `edges="edges"` keyword to the node-link serialisation call so
the wire key is deterministic regardless of the resolved networkx version, rather than
relying on the installed default.

`S02` raised the `networkx` dependency floor from `>=3.4` to `>=3.6` (the version where
the `edges` node-link key became the default) and re-locked; only the recorded specifier
moved, no resolved package version changed.

`S03` eliminated the duplicate metrics computation on the JSON export path by threading
the already-built subgraph into `metrics` through a private parameter, so the
`O(V*E)` betweenness centrality runs once per `to_dict` call instead of twice, with no
change to the output shape.

`S04` bumped the graph envelope schema to `vaultspec.vault.graph.v2` by adding an
optional `version` parameter to the shared `json_envelope` helper that defaults to 1, so
every other caller keeps emitting `v1` unchanged while the graph command emits `v2`. The
user confirmed at the ADR gate that no `v1` consumers exist, so no compatibility shim was
written.

`S05` added a full-envelope contract test that asserts the complete `v2` shape with
exact-set equality over the envelope keys, every node field, every edge field, and every
metrics key, so any field added, removed, or renamed without a schema bump fails the
suite.

`S06` added archive-resolution branch tests exercising link resolution against the
archive directory against real on-disk fixtures.

`S07` added feature-scoped centrality assertions and replaced an early-returning
collision fan-out test with one that constructs a guaranteed stem collision and asserts
the fan-out unconditionally.

Verification: the graph and CLI suites were green at phase close (1125 passed, 0 failed,
0 skipped) and `vault check all` was clean apart from pre-existing unrelated advisories.
Code review returned PASS with no critical or high findings; the medium and low notes
(plan-scope-accuracy on `S04`, an optional extra archive unit test, naming nits) were
recorded as non-blocking.
