---
tags:
  - '#plan'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
tier: L2
related:
  - '[[2026-07-27-vault-scale-performance-adr]]'
  - '[[2026-07-27-vault-scale-performance-audit]]'
---

# `vault-scale-performance` plan

Execute the accepted large-vault performance architecture: racily-clean cache
validation, counts-vs-analysis API split, single-ingress check pipeline,
run-scoped workspace facts, report caps, and the synthetic-corpus scale gate.

## Description

This plan executes the accepted decisions of the authorizing ADR (see
`related:`): D1 and D2 and D7 land in Phase P01 (graph cache validation policy,
descriptive-counts split, warm-read defaults), D3 and D4 land in Phase P02 (the
single-ingress check pipeline contract and the workspace-facts-read-once rule,
including every point fix the grounding audit validated byte-identical), and D5
and D6 land in Phase P03 (report volume caps and the synthetic-corpus
complexity regression gate). The measured evidence behind every step lives in
the grounding audit; behaviour preservation is the hard boundary except for the
two explicitly decided surface changes (report caps, opt-in analysis).

## Steps

### Phase `P01` - graph and cache

Deliver the D1 racily-clean cache validation, the D2 counts-vs-analysis API split, and the D7 warm-read defaults so graph-backed verbs stop paying cold-build and all-pairs-analysis costs.

- [x] `P01.S01` - rework fingerprint_vault to the racily-clean rule: trust size+mtime, hash only manifest-write-tick files, keep full-hash as opt-in deep verification; `src/vaultspec_core/graph/cache.py`.
- [x] `P01.S02` - add a cheap descriptive-counts surface and route the render_tree title through it, keeping graph-theoretic metrics opt-in; `src/vaultspec_core/graph/api.py`.
- [x] `P01.S03` - default the MCP find graph build to the warm cache; `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `P01.S04` - reuse the already-built graph and single scan in the status stats path instead of a second VaultGraph build and rescans; `src/vaultspec_core/vaultcore/orientation.py`.
- [x] `P01.S05` - classify type-filtered listings by path arithmetic instead of parsing every document; `src/vaultspec_core/vaultcore/query.py`.

### Phase `P02` - single-ingress check pipeline

Enforce the D3 single-ingress contract and the D4 workspace-facts-read-once rule across the check suite so the calculate phase runs entirely from the shared snapshot.

- [x] `P02.S06` - extend the corpus snapshot with raw bytes and per-file metadata so every check can run from it; `src/vaultspec_core/vaultcore/models.py`.
- [x] `P02.S07` - route the annotations check through the shared snapshot; `src/vaultspec_core/vaultcore/checks/annotations.py`.
- [x] `P02.S08` - route the markdown check through the shared snapshot; `src/vaultspec_core/vaultcore/checks/markdown.py`.
- [x] `P02.S09` - route the encoding check through snapshot raw bytes, folding it into the single ingress read; `src/vaultspec_core/vaultcore/checks/encoding.py`.
- [x] `P02.S10` - route the feature rename integrity check through the shared snapshot; `src/vaultspec_core/vaultcore/checks/feature_rename_integrity.py`.
- [x] `P02.S11` - exempt the rename integrity check from the single-ingress contract: it validates workspace resources under .vaultspec/, not the vault corpus, so no snapshot routing applies; `src/vaultspec_core/vaultcore/checks/rename_integrity.py`.
- [x] `P02.S12` - memoize per-plan step-id parsing and drop redundant disk probes in the exec mapping check; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.
- [x] `P02.S13` - precompute index existence and per-feature counts in one snapshot pass, removing the O(features x documents) scan; `src/vaultspec_core/vaultcore/checks/features.py`.
- [x] `P02.S14` - memoize the baseline ledger to one read per run and drop per-document path resolution; `src/vaultspec_core/vaultcore/body_schema.py`.
- [x] `P02.S15` - eliminate the per-document path-syscall storm in the body sections check; `src/vaultspec_core/vaultcore/checks/body_sections.py`.
- [x] `P02.S16` - add the single-ingress enforcement test that fails any check touching disk after ingress; `src/vaultspec_core/vaultcore/checks/tests/test_single_ingress.py`.

### Phase `P03` - report volume and scale gate

Apply the D6 report volume caps and land the D5 synthetic-corpus complexity regression gate.

- [x] `P03.S17` - cap the check report phase with marked truncation and aggregates and a fixed console geometry; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S18` - cap the unscoped vault graph tree render with marked truncation; `src/vaultspec_core/graph/api.py`.
- [x] `P03.S19` - add the synthetic-corpus complexity scale gate asserting operation counts and cross-size scaling ratios under a dedicated marker; `src/vaultspec_core/tests/scale/test_scale_gate.py`.

### Phase `P04` - native leaf acceleration

Deliver the D8 native leaf libraries: verify the shipped libyaml loader engages on the parse hot path and route the opt-in betweenness analysis through a C-backed graph library with a pure networkx fallback.

- [x] `P04.S20` - verify the shipped libyaml CSafeLoader seam engages on the frontmatter hot path and record the measured parse gain; `src/vaultspec_core/vaultcore/parser.py`.
- [x] `P04.S21` - route the opt-in betweenness analysis through rustworkx with a networkx fallback and add the dependency; `src/vaultspec_core/graph/api.py`.
- [x] `P04.S22` - add the engine parity test asserting rustworkx and networkx betweenness agree on the synthetic corpus; `src/vaultspec_core/graph/tests/test_analysis_engine.py`.

## Parallelization

P01 and P02 are independent of each other and may run in parallel; within P02,
S06 (the snapshot extension) is a hard prerequisite for S07 through S11 and
S16, while S12 through S15 are independent point fixes. P03 depends on both
earlier phases: S17 and S18 cap surfaces P01 and P02 touch, and S19 gates the
complexity budgets they establish.

## Verification

- The full unit gate passes: `pytest src/vaultspec_core -m unit`.
- Check, graph, status, and list verb outputs are byte-identical to baseline on
  an unchanged corpus, except the two decided surface changes (report caps and
  opt-in analysis), which ship with their own tests.
- The single-ingress enforcement test proves no checker touches disk during the
  calculate phase.
- The scale gate asserts the operation-count budgets and cross-size scaling
  ratios on generated synthetic corpora under its dedicated marker.
- `vault check all` stays clean for the feature's documents; the plan is
  complete when every Step row is closed.
