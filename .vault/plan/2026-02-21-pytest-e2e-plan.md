---
tags:
  - '#plan'
  - '#pytest-e2e'
date: '2026-02-21'
tier: L1
related:
  - '[[2026-02-21-pytest-e2e-observability-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:37c16d20182e4d8924c9a239017a9e293e9c9bbfb9028fc6eb3dde8cfe19fff2'
---

# `pytest-e2e` plan

Add an observability and reliability stack for long-running A2A end-to-end tests.

## Description

Reconstructed 2026-09-19 from this feature's historical execution records
(`2026-02-21-pytest-e2e-impl-phase1-exec`, `2026-02-21-pytest-e2e-impl-phase2-exec`,
`2026-02-21-pytest-e2e-impl-phase3-exec`, `2026-02-21-pytest-e2e-impl-summary-exec`),
which recorded completed work against a plan
(`2026-02-21-pytest-e2e-observability-impl-plan`) that no longer survives. The Steps
below restate what those records report as done; they are closed on that evidence, not
re-executed. Phase 2's evidence also records a deviation: `pytest-harvest` was added
then removed after live validation showed it incompatible with `pytest-rerunfailures`,
and structured logging replaced it. Authorization is historical: the work shipped in
February 2026 under the observability stack the ADR authorizes.

Decision coverage: `2026-02-21-pytest-e2e-observability-adr` governs the retry and
logging stack this plan sequences.

## Steps

- [x] `S01` - add pytest observability config, timeout handling, the flaky marker, and three new test dependencies; `pyproject.toml`.
- [x] `S02` - instrument E2E test classes with flaky retry markers and structured logging, replacing the incompatible pytest-harvest results_bag fixture; `src/vaultspec/protocol/a2a/tests/test_e2e_a2a.py`.
- [x] `S03` - gitignore the new event log output and verify fast-suite and E2E collection integrity; `.gitignore`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report them, and
the work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: `uv sync --group dev` installed cleanly at S01, the fast suite passed 381/381 at S02 and S03, and a live
E2E run against Claude confirmed the observability stack captured logs, JSONL events,
and a rate-limit error with full traceback. The E2E test files sit under the pre-rename
`src/vaultspec/` tree and are not re-checkable at their original locators.
