---
tags:
  - '#plan'
  - '#framework-reword'
date: '2026-09-08'
tier: L1
related:
  - '[[2026-09-08-framework-reword-adr]]'
modified: '2026-09-08'
body_schema: body-v2
body_hash: 'sha256:d087a2688dc1cb9eb9e0d471657461d2308ed0d5345e8beed59bcd5a5a166019'
---

# `framework-reword` plan

## Description

Approved 2026-09-08

Implement `2026-09-08-framework-reword-adr` in four cohesive revisions. The user approved the reported policy and major Steps and authorized implementation and in-scope review corrections. Keep a flat L1 sequence.

## Steps

- [x] `S01` - Normalize routing, decision coverage, approval, evidence, sizing, and review policy; `src/vaultspec_core/builtins/system, src/vaultspec_core/builtins/rules`.
- [ ] `S02` - Align skills, personas, and templates with cohesive execution and tier-aware review; `src/vaultspec_core/builtins/skills, src/vaultspec_core/builtins/agents, src/vaultspec_core/builtins/templates`.
- [ ] `S03` - Align lifecycle validation, repair, and ADR transitions with decision coverage; `src/vaultspec_core/vaultcore, src/vaultspec_core/cli, src/vaultspec_core/mcp_server`.
- [ ] `S04` - Verify integrated routing scenarios, synchronize bundled outputs, and resolve cohesive Astra review findings; `src/vaultspec_core, dev/guards, docs, .vaultspec`.

## Parallelization

Implementation is sequential. The independent Astra reviewer prepares criteria now and reviews the integrated result at completion. No concurrent source writers.

## Verification

Focused regression scenarios cover decision-free plans, ADR reuse, draft and active status, transitive evidence, safe supersession, and historical records. Run relevant tests, lint, type and vault checks, verify synchronization and provider outputs, and resolve findings from one cohesive Astra review covering plan close and handoff.
