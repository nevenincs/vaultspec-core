---
tags:
  - '#plan'
  - '#graph-hardening'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-03-22-graph-hardening-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:7e0992e107984683e71393923740493f00f4b86046b6976a59ecc2a5c95b93ea'
---

# `graph-hardening` plan

Give the vault graph phantom nodes and a dangling-link checker mirroring Obsidian's "not created" link model.

## Description

Reconstructed 2026-09-19 from this feature's six historical execution records
(`2026-03-22-graph-hardening-phase1-exec` through `-phase4-exec`, `-phase6-exec`,
and `-summary-exec`), which recorded completed work but had no surviving plan to
attribute it to. The Steps below restate what those records report as done; they
are closed on that evidence, not re-executed. Step S05 (the pre-commit gate and
orphan-checker guard) has no dedicated phase record; its evidence is the summary
record's own Files Modified list, since no `-phase5-exec` record exists.
Authorization is historical: the work is governed by the accepted
`2026-03-22-graph-hardening-adr`, which this plan links in `related:`.

Decision coverage: the governing decision is `2026-03-22-graph-hardening-adr`
(accepted), which records phantom nodes as first-class graph citizens, the
`check_dangling` checker, and the phantom-aware guards this plan's Steps
implement.

## Steps

- [x] `S01` - add phantom node support to the vault graph for unresolved wiki-link targets; `src/vaultspec_core/graph/api.py`.
- [x] `S02` - add phantom-aware metrics and guard existing checkers against phantom nodes; `src/vaultspec_core/vaultcore/checks/references.py`.
- [x] `S03` - render phantom nodes distinctly in the tree, JSON, and CLI metrics output; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `S04` - add the check_dangling checker for dangling wiki-links with --fix support; `src/vaultspec_core/vaultcore/checks/dangling.py`.
- [x] `S05` - prepare the pre-commit dangling-link gate and the phantom-aware orphan guard; `.pre-commit-config.yaml`.
- [x] `S06` - add test coverage for phantom nodes, checker guards, rendering, and the dangling checker; `src/vaultspec_core/graph/tests/test_graph.py`.

## Parallelization

None. The Steps are recorded sequentially as the historical phase records
report them, and the work is complete, so no container is available for
concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: 749
project tests passing with no regressions, ruff and ty clean, and the live
vault reporting phantom nodes and dangling links at the counts each record
states.
