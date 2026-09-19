---
tags:
  - '#plan'
  - '#audit-fixes'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-02-22-audit-fixes-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:e82896b09b2e04619ce5e02a8e84bf52a1105498c4a7520713272a126f6f96bc'
---

# `audit-fixes` plan

Remediate the RAG, CLI logging, and hydration findings raised by the codebase audit.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-02-22-audit-fixes-execution-summary-exec`), which recorded completed work but
had no surviving plan to attribute it to. The Steps below restate what that record
reports as done; they are closed on its evidence, not re-executed. Authorization is
historical: the work shipped in February 2026 under the audit remediation it names.

Decision coverage: no costly decision is involved and no ADR governs this remediation.
It applies settled constraints already recorded for the feature.

## Steps

- [x] `S01` - harden RAG entry points against a missing GPU and report the filesystem fallback; `src/vaultspec/rag/api.py`.
- [x] `S02` - centralise CLI logging and replace informational prints with logger calls; `src/vaultspec/cli.py`.
- [x] `S03` - support both placeholder styles in hydration and warn on unhydrated keys; `src/vaultspec/vaultcore/hydration.py`.

## Parallelization

None. The Steps are recorded sequentially as the historical record reports them, and
the work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs. The paths it
names sit under the pre-rename `src/vaultspec/` tree and were carried forward by the
later package restructure, so they are not re-checkable at their original locators.
