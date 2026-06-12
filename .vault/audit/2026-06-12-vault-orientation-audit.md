---
tags:
  - '#audit'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-vault-orientation-plan]]'
  - '[[2026-06-12-vault-orientation-adr]]'
---

# `vault-orientation` audit: `implementation code review`

## Scope

Verify-phase review of the complete vault-orientation implementation: 35 plan steps
across three waves (modified-stamp foundation, status rollup and grounding verb,
firmware and documentation), spanning the vaultcore model and checks, the plan status
core, the orientation module, the `vault status` CLI verb, the backfill migration, the
graph cache, and the firmware surfaces. Reviewed against ADR decisions D1 through D8
across four domains: safety, intent, quality, and cross-cutting concerns.

## Findings

Status: **PASS**. No critical or high findings; twelve low-level findings, all
confirmations of sound implementation or non-blocking notes.

### stamp-helper-convergence | low | one canonical date surface

All five mutator sites and both scaffold and check paths route date logic through
`parse_lenient_date`, `normalize_date`, and `refresh_modified_stamp`. The checker and
repair pipeline carry a distinct writer deliberately: they must preserve a non-today
parsed value, which the always-today mutator helper cannot. Documented split, not
drift.

### stamp-stability-and-encoding | low | idempotent refresh, byte-true encodings

Same-day refresh is a verified fixed point; CRLF documents round-trip with CRLF only; a
leading BOM survives stamping. The date-line-as-last-frontmatter-line edge is guarded
in both writers.

### hostile-date-input-safety | low | adversarial values never raise

`parse_lenient_date` returns None for empty, non-string, impossible, and ambiguous
values; the checker surfaces unparseable stamps as non-fixable errors and never drops
them; the rollup falls back date-then-filename and sorts undateable documents last.

### empty-vault-arithmetic | low | division guards verified

The clone-signature ratio divides only when stat-able documents exist; completion
percent guards the stepless plan; an empty vault rolls up to empty structures.

### migration-idempotence | low | strictly additive backfill

The backfill skips stamped documents, never normalizes existing values, is byte-stable
and a counted no-op on second run, and raises on I/O failure so the version manifest is
not falsely bumped.

### case-only-rename-guard | low | fail-closed on case-insensitive filesystems

Both restamp writers confirm exact-case presence via a parent-directory listing before
writing, skipping on mismatch rather than resurrecting stale casing.

### graph-cache-schema-bump | low | v3 invalidates cleanly

Old caches read as a miss under the bumped schema string; the graph node carries
`modified` verbatim so the checker can distinguish noncanonical from missing.

### d5-no-graph-leakage | low | stems and scalars only

The trace traverses the graph internally but every returned structure holds stems,
booleans, and grouped string lists; no graph types, edges, or metrics cross the CLI
boundary. Mtime is never presented as recency.

### d4-limit-since-semantics | low | as decided

Count default truncates to the last N; the day window keeps everything inside the
horizon and excludes undated documents; the reference day is injectable for
deterministic tests.

### d8-firmware-parity | low | firmware names only shipped surfaces

The orientation mandate names `vaultspec-core vault status [TARGET]` across the rule,
system fragment, and references; the language-contract and reference-drift suites pass.

### test-integrity | low | real files, no doubles

All six new test files build genuine vaults in temporary directories; no mocks,
patches, stubs, skips, or tautologies; the fresh-context regression test exercises the
real CLI in an uninitialised context.

### batched-core-performance | low | one scan, one parse

One exec-record scan and one parse per plan back both the rollup and the single-plan
path. Non-blocking note: the trace mode builds its own exec index, but rollup and trace
are mutually exclusive per invocation, so no redundant scan occurs in practice.

## Recommendations

None blocking. Safe to merge. The trace-mode exec-index note above is a candidate
micro-refactor if the two modes ever compose in one invocation. The full test suite
passes (2105 tests, exit 0) alongside the review.

## Codification candidates

None. The orientation bootstrap mandate already shipped as builtin firmware in this
feature (decision D8), and the stamp discipline is deliberately not rule-codified per
decision D3a (CLI-enforced; a rule would be tautological context cost).
