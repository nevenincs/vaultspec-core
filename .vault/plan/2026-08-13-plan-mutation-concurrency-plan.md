---
tags:
  - '#plan'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
tier: L2
related:
  - '[[2026-08-13-plan-mutation-concurrency-adr]]'
  - '[[2026-08-13-plan-mutation-concurrency-research]]'
  - '[[2026-08-13-plan-mutation-concurrency-reference]]'
modified: '2026-08-23'
body_hash: 'sha256:9779ecbec79a367aee9ccdd394b5a31bb3065357e34bd00a141e103ba126da01'
---

# `plan-mutation-concurrency` plan

## Description

Implement the accepted lock-scoped plan mutation transaction across the plan core,
CLI, and MCP surfaces. The research and reference establish the current lost-update
window and the existing locking primitives; the ADR authorizes per-document locking
across the full read-modify-write lifecycle while preserving atomic replacement,
identifier guards, output schemas, and independent-plan concurrency.

## Steps

### Phase `P01` - Shared mutation transaction

Establish one lock-scoped owner for plan load, mutation, persistence, and verification.

- [x] `P01.S01` - Implement the typed per-document plan mutation transaction and focused real-behavior tests; `src/vaultspec_core/plan/mutation_transaction.py, src/vaultspec_core/tests/plan/test_mutation_transaction.py`.

### Phase `P02` - Surface convergence

Route every CLI and MCP plan mutator through the shared transaction and prove cross-process preservation.

- [x] `P02.S02` - Converge CLI plan mutation commands on the shared transaction owner; `src/vaultspec_core/cli plan command modules`.
- [x] `P02.S03` - Converge MCP plan edits and add cross-process lost-update regression coverage; `src/vaultspec_core/mcp_server/tools/plan.py, src/vaultspec_core/tests/plan/test_mutation_concurrency.py`.

### Phase `P03` - Ratchets and delivery

Burn down strict typing, quality, documentation, drift, review, and PR gates to verified closure.

- [x] `P03.S04` - Run strict ratchets, remediate review findings, and complete PR and issue delivery; `repository quality gates and GitHub pull request`.

## Parallelization

P01 establishes the shared owner and lands first. P02.S02 and P02.S03 may then proceed
independently because they adapt separate presentation surfaces, but both must land
before P03.S04 runs repository-wide ratchets and delivery gates.

## Verification

- Real cross-process CLI mutation coverage proves concurrent additions to one plan both
  survive with distinct canonical identifiers.
- Focused plan, CLI, and MCP suites pass without fakes, mocks, stubs, patches,
  monkeypatching, skips, or xfails.
- Strict Ruff and type-checking ratchets report no new or remaining findings in scope.
- Full configured test, documentation, vault-integrity, and codebase-drift gates pass,
  with any unrelated pre-existing diagnostics reported precisely.
- Mandatory code review has no unresolved HIGH or CRITICAL finding.
- The branch contains only issue 296 changes; the PR is green and merged, and issue 296
  is closed with the delivered guarantees recorded.
