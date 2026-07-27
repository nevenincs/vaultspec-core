---
tags:
  - '#plan'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
tier: L2
related:
  - '[[2026-07-27-adr-topic-infix-adr]]'
  - '[[2026-07-27-adr-topic-infix-research]]'
  - '[[2026-07-27-adr-topic-infix-reference]]'
---

# `adr-topic-infix` plan

Admit topic-infixed ADR records without changing plan or execution-record identity.

## Description

This plan implements the accepted `2026-07-27-adr-topic-infix-adr` decision. Phase
P01 converges the creator and both transports on ADR admission; Phase P02 locks the
workflow with direct, CLI, and MCP behavior tests and aligns the owned rule text.

## Steps

### Phase `P01` - admit ADR topics at every creation boundary

Converge the shared creator, CLI, and MCP on the accepted four-type admission set.

- [x] `P01.S01` - Extend the shared topic-infix admission set to ADR documents; `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `P01.S02` - Align CLI topic validation and help text with ADR admission; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S03` - Align MCP topic schema and validation with ADR admission; `src/vaultspec_core/mcp_server/tools/documents.py`.

### Phase `P02` - prove behavior and synchronize the contract

Lock the same-day ADR workflow with real tests and update the owned rule/reference surfaces.

- [x] `P02.S04` - Cover direct scaffolder creation and duplicate rejection for topic-infixed ADRs; `src/vaultspec_core/vaultcore/tests/test_hydration.py`.
- [ ] `P02.S05` - Cover CLI creation of two same-day topic-infixed ADRs; `tests/test_commands.py`.
- [ ] `P02.S06` - Cover MCP creation of topic-infixed ADRs in a mixed batch; `tests/unit/mcp_server/test_create_tool.py`.
- [ ] `P02.S07` - Revise the owned topic-infix rule and regenerate its published reference; `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.

## Parallelization

The P01 changes are coupled through one admission set and land together. P02.S04,
P02.S05, and P02.S06 may be prepared independently after P01; P02.S07 follows the
settled wording and can run alongside the tests.

## Verification

The plan is complete when all seven Steps are checked, direct scaffolding creates two
same-day ADR topics while duplicate topics fail, CLI and MCP create the same shape,
the owned rule/reference surfaces agree, focused tests pass, and implementation review
finds no transport or documentation drift.
