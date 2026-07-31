---
generated: true
tags:
  - '#index'
  - '#vault-scale-performance'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:0d4d7bdf836659325c235ec5301a23196dfa0741944ed8acd32faf5ee0f7779d'
related:
  - '[[2026-07-27-vault-scale-performance-P01-S01]]'
  - '[[2026-07-27-vault-scale-performance-P01-S02]]'
  - '[[2026-07-27-vault-scale-performance-P01-S03]]'
  - '[[2026-07-27-vault-scale-performance-P01-S04]]'
  - '[[2026-07-27-vault-scale-performance-P01-S05]]'
  - '[[2026-07-27-vault-scale-performance-P01-summary]]'
  - '[[2026-07-27-vault-scale-performance-P02-S06]]'
  - '[[2026-07-27-vault-scale-performance-P02-S07]]'
  - '[[2026-07-27-vault-scale-performance-P02-S08]]'
  - '[[2026-07-27-vault-scale-performance-P02-S09]]'
  - '[[2026-07-27-vault-scale-performance-P02-S10]]'
  - '[[2026-07-27-vault-scale-performance-P02-S11]]'
  - '[[2026-07-27-vault-scale-performance-P02-S12]]'
  - '[[2026-07-27-vault-scale-performance-P02-S13]]'
  - '[[2026-07-27-vault-scale-performance-P02-S14]]'
  - '[[2026-07-27-vault-scale-performance-P02-S15]]'
  - '[[2026-07-27-vault-scale-performance-P02-S16]]'
  - '[[2026-07-27-vault-scale-performance-P02-summary]]'
  - '[[2026-07-27-vault-scale-performance-P03-S17]]'
  - '[[2026-07-27-vault-scale-performance-P03-S18]]'
  - '[[2026-07-27-vault-scale-performance-P03-S19]]'
  - '[[2026-07-27-vault-scale-performance-P03-summary]]'
  - '[[2026-07-27-vault-scale-performance-P04-S20]]'
  - '[[2026-07-27-vault-scale-performance-P04-S21]]'
  - '[[2026-07-27-vault-scale-performance-P04-S22]]'
  - '[[2026-07-27-vault-scale-performance-P04-summary]]'
  - '[[2026-07-27-vault-scale-performance-adr]]'
  - '[[2026-07-27-vault-scale-performance-audit]]'
  - '[[2026-07-27-vault-scale-performance-implementation-audit]]'
  - '[[2026-07-27-vault-scale-performance-plan]]'
---

# `vault-scale-performance` feature index

Auto-generated index of all documents tagged with `#vault-scale-performance`.

## Documents

### adr

- `2026-07-27-vault-scale-performance-adr` - `vault-scale-performance` adr: `large-vault performance architecture` | (**status:** `accepted`)

### audit

- `2026-07-27-vault-scale-performance-audit` - `vault-scale-performance` audit: `large-vault command latency`
- `2026-07-27-vault-scale-performance-implementation-audit` - `vault-scale-performance` audit: `implementation`

### exec

- `2026-07-27-vault-scale-performance-P01-S01` - rework fingerprint_vault to the racily-clean rule: trust size+mtime, hash only manifest-write-tick files, keep full-hash as opt-in deep verification
- `2026-07-27-vault-scale-performance-P01-S02` - add a cheap descriptive-counts surface and route the render_tree title through it, keeping graph-theoretic metrics opt-in
- `2026-07-27-vault-scale-performance-P01-S03` - default the MCP find graph build to the warm cache
- `2026-07-27-vault-scale-performance-P01-S04` - reuse the already-built graph and single scan in the status stats path instead of a second VaultGraph build and rescans
- `2026-07-27-vault-scale-performance-P01-S05` - classify type-filtered listings by path arithmetic instead of parsing every document
- `2026-07-27-vault-scale-performance-P01-summary` - `vault-scale-performance` `P01` summary
- `2026-07-27-vault-scale-performance-P02-S06` - extend the corpus snapshot with raw bytes and per-file metadata so every check can run from it
- `2026-07-27-vault-scale-performance-P02-S07` - route the annotations check through the shared snapshot
- `2026-07-27-vault-scale-performance-P02-S08` - route the markdown check through the shared snapshot
- `2026-07-27-vault-scale-performance-P02-S09` - route the encoding check through snapshot raw bytes, folding it into the single ingress read
- `2026-07-27-vault-scale-performance-P02-S10` - route the feature rename integrity check through the shared snapshot
- `2026-07-27-vault-scale-performance-P02-S11` - exempt the rename integrity check from the single-ingress contract: it validates workspace resources under .vaultspec/, not the vault corpus, so no snapshot routing applies
- `2026-07-27-vault-scale-performance-P02-S12` - memoize per-plan step-id parsing and drop redundant disk probes in the exec mapping check
- `2026-07-27-vault-scale-performance-P02-S13` - precompute index existence and per-feature counts in one snapshot pass, removing the O(features x documents) scan
- `2026-07-27-vault-scale-performance-P02-S14` - memoize the baseline ledger to one read per run and drop per-document path resolution
- `2026-07-27-vault-scale-performance-P02-S15` - eliminate the per-document path-syscall storm in the body sections check
- `2026-07-27-vault-scale-performance-P02-S16` - add the single-ingress enforcement test that fails any check touching disk after ingress
- `2026-07-27-vault-scale-performance-P02-summary` - `vault-scale-performance` `P02` summary
- `2026-07-27-vault-scale-performance-P03-S17` - cap the check report phase with marked truncation and aggregates and a fixed console geometry
- `2026-07-27-vault-scale-performance-P03-S18` - cap the unscoped vault graph tree render with marked truncation
- `2026-07-27-vault-scale-performance-P03-S19` - add the synthetic-corpus complexity scale gate asserting operation counts and cross-size scaling ratios under a dedicated marker
- `2026-07-27-vault-scale-performance-P03-summary` - `vault-scale-performance` `P03` summary
- `2026-07-27-vault-scale-performance-P04-S20` - verify the shipped libyaml CSafeLoader seam engages on the frontmatter hot path and record the measured parse gain
- `2026-07-27-vault-scale-performance-P04-S21` - route the opt-in betweenness analysis through rustworkx with a networkx fallback and add the dependency
- `2026-07-27-vault-scale-performance-P04-S22` - add the engine parity test asserting rustworkx and networkx betweenness agree on the synthetic corpus
- `2026-07-27-vault-scale-performance-P04-summary` - `vault-scale-performance` `P04` summary

### plan

- `2026-07-27-vault-scale-performance-plan` - `vault-scale-performance` plan
