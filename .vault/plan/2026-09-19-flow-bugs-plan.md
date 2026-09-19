---
tags:
  - '#plan'
  - '#flow-bugs'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-04-21-flow-bugs-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:df5c90603bf652f16da4129b5ec45ff107e28d01d01bb721b3102a1c740f3dfc'
---

# `flow-bugs` plan

Fix five install-layer defects reported against the framework installer, gitignore, and structure checker.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-04-21-flow-bugs-phase-1-summary-exec`), which recorded completed work
but had no surviving plan to attribute it to. The Steps below restate the
five domains that record reports as implemented, tested, and green; they
are closed on that evidence, not re-executed. Authorization is historical:
the work shipped in April 2026 fixing GitHub issue #80.

Decision coverage: `[[2026-04-21-flow-bugs-adr]]` governs the fix approach
for each of the five domains this plan sequences.

## Steps

- [x] `S01` - untrack legacy committed provider artifacts and lock sentinels on install; `src/vaultspec_core/core/commands.py`.
- [x] `S02` - emit lock-sentinel gitignore entries when the framework is installed; `src/vaultspec_core/core/gitignore.py`.
- [x] `S03` - short-circuit precommit scaffolding when prek.toml is already present; `src/vaultspec_core/core/commands.py`.
- [x] `S04` - stop staged deletions from blocking remediation commits; `src/vaultspec_core/core/commands.py`.
- [x] `S05` - rewrite related wiki-link references after a structure-check rename; `src/vaultspec_core/vaultcore/checks/structure.py`.

## Parallelization

None. The five domains landed together on one branch as a single reviewed
change set, and the work is complete, so no container is available for
concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs: the
nineteen-case `test_flow_bugs.py` suite, the extended `test_gitignore.py`
suite, and the full adjacent test suite all reported green, with `ruff check` and `ty check` clean and a post-implementation code review's one
HIGH and three MEDIUM findings addressed before merge.
