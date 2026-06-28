---
tags:
  - '#plan'
  - '#curator-reframe'
date: '2026-06-28'
modified: '2026-06-28'
tier: L2
related:
  - '[[2026-06-28-curator-reframe-adr]]'
  - '[[2026-06-28-curator-reframe-research]]'
---

# `curator-reframe` plan

Reframe the curator to ADR architecture reconciliation and encode the canonical status taxonomy it enforces.

## Description

This plan delivers the curator reframe decided in the ADR and grounded in the research.
Phase P01 (the skill and agent rewrite) is already complete; it is recorded here as the
binding history. The remaining phases encode the canonical ADR status taxonomy in the
core library as a single source of truth, reconcile the ADR template and the
`adr_supersede` writer to it, add the `adr-status` validator to the `vault check` suite,
cover the new code with unit-marked factory-based tests, and finalize the skill
references to treat the validator as present. The authorizing ADR and research are in the
`related:` frontmatter.

## Steps

### Phase `P01` - reframe the curator skill and agent

Rewrite the builtin skill and agent persona to ADR architecture reconciliation.

- [x] `P01.S01` - rewrite the curate skill to ADR reconciliation; `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`.
- [x] `P01.S02` - add the status-taxonomy and reconciliation-playbook references; `src/vaultspec_core/builtins/skills/vaultspec-curate/references/`.
- [x] `P01.S03` - rewrite the docs-curator agent persona; `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.

### Phase `P02` - encode the canonical status taxonomy in core

Define the AdrStatus enum and reconcile the supersede writer and ADR template to it.

- [x] `P02.S04` - add the AdrStatus canonical status enum; `src/vaultspec_core/core/enums.py`.
- [x] `P02.S05` - reconcile adr_supersede to write the enum value; `src/vaultspec_core/core/adr.py`.
- [x] `P02.S06` - reconcile the ADR template status comment and H1 placeholder; `src/vaultspec_core/builtins/templates/adr.md`.

### Phase `P03` - add the adr-status validator check

Implement, register, and CLI-wire the adr-status health check.

- [x] `P03.S07` - implement the check_adr_status checker; `src/vaultspec_core/vaultcore/checks/adr_status.py`.
- [x] `P03.S08` - register the checker in the suite and run_all_checks; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P03.S09` - wire vault check adr-status into the CLI group; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P04` - tests, finalize references, and verify

Cover the new code with unit tests, finalize skill references, and run the gate.

- [x] `P04.S10` - add unit tests for the enum and supersede enum write; `src/vaultspec_core/core/tests/`.
- [x] `P04.S11` - add unit tests for check_adr_status; `src/vaultspec_core/vaultcore/checks/tests/`.
- [x] `P04.S12` - finalize skill references to treat the validator as present; `src/vaultspec_core/builtins/skills/vaultspec-curate/references/adr-status-taxonomy.md`.
- [x] `P04.S13` - run the unit gate, sync, and spec doctor; `src/vaultspec_core/`.

## Parallelization

Phase P01 is already complete. Phase P02 (the core taxonomy) must land before Phase P03
(the validator), because the validator imports the enum. Within P02 the enum step
precedes the supersede and template reconciliations. Phase P03 steps are sequential
(implement, then register, then wire the CLI). Phase P04 tests can be authored in
parallel once their targets exist, but the unit gate runs last.

## Verification

The plan is complete when every Step is closed. Success criteria: the `AdrStatus` enum
exists and is the single definition imported by the supersede writer and the validator;
`vault check adr-status` runs, validates the corpus against the canonical set, and
reports the legacy-encoding and divergence findings without hard-failing the suite; the
ADR template status comment and H1 placeholder match the enum; the unit gate
(`pytest src/vaultspec_core -m unit`) passes with factory-based real-filesystem tests and
no mocks or skips; `vaultspec-core sync` and `spec doctor` are clean; and the skill
references no longer describe the validator as forthcoming.
