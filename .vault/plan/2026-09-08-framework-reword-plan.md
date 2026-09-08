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
body_hash: 'sha256:3718cfbcfc408bf51c13e28830521dbc3e52a62f9f8953a2bd9369903eda1dc4'
---

# `framework-reword` plan

## Description

Approved 2026-09-08

Implement `2026-09-08-framework-reword-adr` in four cohesive revisions. The user approved the reported policy and major Steps and authorized implementation and in-scope review corrections. Keep a flat L1 sequence.

## Steps

- [x] `S01` - Normalize routing, decision coverage, approval, evidence, sizing, and review policy; `src/vaultspec_core/builtins/system, src/vaultspec_core/builtins/rules`.
- [x] `S02` - Align skills, personas, and templates with cohesive execution and tier-aware review; `src/vaultspec_core/builtins/skills, src/vaultspec_core/builtins/agents, src/vaultspec_core/builtins/templates`.
- [x] `S03` - Align lifecycle validation, repair, and ADR transitions with decision coverage; `src/vaultspec_core/vaultcore, src/vaultspec_core/core, src/vaultspec_core/cli, src/vaultspec_core/mcp_server, src/vaultspec_core/plan, src/vaultspec_core/tests, src/vaultspec_core/builtins/reference/cli.md, docs/CLI.md`.
- [ ] `S04` - Verify integrated routing scenarios, synchronize bundled outputs, and resolve cohesive Astra review findings; `src/vaultspec_core, dev/guards, docs, .vaultspec`.

## Parallelization

Implementation is sequential. The independent Astra reviewer prepares criteria now and reviews the integrated result at completion. No concurrent source writers.

## Verification

Focused regression scenarios cover decision-free plans, ADR reuse, draft and active status, transitive evidence, safe supersession, and historical records. Run relevant tests, lint, type and vault checks, verify synchronization and provider outputs, and resolve findings from one cohesive Astra review covering plan close and handoff.
