---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# `graph-backend` `P02` summary

Phase `P02` delivered connection strengths with zero new runtime dependencies. Explicit
graph edges now carry provenance, multiplicity, and a normalised weight; a separate
derived relatedness edge set carries reciprocity, shared-tag, and networkx
link-prediction signals without ever polluting the canonical checker-facing graph;
nodes carry pagerank and in-degree size hints; and the graph verb gained local-graph ego
scoping. All of this is emitted through the version 2 payload. The phase passed code
review after a remediation pass that closed two high findings.

- Modified: `src/vaultspec_core/vaultcore/links.py`
- Modified: `src/vaultspec_core/vaultcore/__init__.py`
- Modified: `src/vaultspec_core/vaultcore/tests/test_links.py`
- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/graph/tests/test_graph.py`
- Modified: `src/vaultspec_core/graph/tests/test_contract.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/builtins/reference/cli.md`
- Modified: `docs/CLI.md`
- Modified: `src/vaultspec_core/tests/cli/test_vault_cli.py`
- Created: `src/vaultspec_core/graph/derived.py`
- Created: `src/vaultspec_core/graph/tests/test_derived.py`
- Created: `src/vaultspec_core/graph/tests/test_pagerank.py`

## Description

`S08` changed the link extractors to preserve multiplicity by returning a `Counter`, so
a target cited several times retains its count; the combine step sums body and related
counts naturally.

`S09` audited and updated every extractor call site for the counted return shape,
preserving target resolution while retaining the per-target count for edge weighting.

`S10` attached a `kind` provenance value (`body`, `related`, or `both`), a `multiplicity`
count, and a normalised `weight` (multiplicity over the maximum multiplicity in the
graph) to every explicit canonical edge.

`S11` created the derived relatedness module computing reciprocity, shared-feature,
shared-tag (directory tags and the feature tag excluded), Jaccard, Adamic-Adar, and
co-citation signals over an undirected real-node projection, composed into a weight by a
documented linear combination with version-pinned coefficients, returned as a separate
structure that never mutates the canonical graph.

`S12` added pagerank and in-degree node-size hints. Because the dependency set ships no
numpy, pagerank is a deterministic pure-Python power iteration faithful to networkx
semantics rather than `nx.pagerank`, honouring the zero-new-dependency constraint.

`S13` added ego-graph local scoping by node and depth for local-graph parity.

`S14` emitted the new explicit edge attributes and the derived edge set in the version 2
payload, with derived edges in their own array, and updated the contract freeze test in
lockstep within the still-unshipped version 2 schema.

`S15` added the `--node`, `--depth`, and derived-edge toggle options to the graph verb
and kept the bundled CLI reference in sync to satisfy the drift guard.

`S16` through `S18` added exact-value tests for multiplicity, edge attributes, and
weights, for every derived signal and the composed weight, and CLI tests for ego scoping
and the derived toggle. `S19` ran the authoritative reference regeneration and provider
sync.

## Outcome

Code review returned REVISION REQUIRED with two high findings, both since resolved: the
pure-Python pagerank shipped without behavioural tests (and its step record overstated
its coverage), and the derived-edge computation ran over the whole graph before
filtering, defeating ego scoping and the scale target. A remediation pass added pagerank
behavioural tests against analytic ground truth (symmetric cycle, star hub, dangling
mass, determinism, empty graph), corrected the step record, fixed a real
insertion-order determinism bug surfaced by the new test, and scoped the derived
computation to the queried node set with an honest statement of which signals are
projection-relative. Re-verification passed (30 targeted tests; full suite green at phase
close, 2119 passed).

## Notes

The synthetic corpus emits only related, multiplicity-1 edges, so the body, both, and
multiplicity-greater-than-one cases are exercised against a crafted real on-disk vault,
not a mock. A latent hash-seed nondeterminism in feature extraction was fixed at the root
(sorting tags before selection); it is behaviourally inert on the current corpus, where
no document carries more than one non-directory tag.
