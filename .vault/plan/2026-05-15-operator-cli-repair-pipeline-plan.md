---
tags:
  - '#plan'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
tier: L2
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-research]]'
  - '[[2026-05-15-operator-cli-repair-pipeline-adr]]'
  - '[[2026-05-15-operator-cli-repair-pipeline-audit]]'
  - '[[2026-05-15-operator-cli-sync-authority-research]]'
  - '[[2026-05-15-operator-cli-sync-authority-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# operator-cli-repair-pipeline plan: operator CLI repair pipeline

## Phases

### Phase `P01` - command contract and navigation

Define the operator-facing command surface and its relationship to existing
commands.

- [x] `P01.S01` - specify command semantics; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S02` - document check-level fix compatibility; `.vaultspec/CLI.md`.
- [x] `P01.S03` - distinguish vault repair from spec doctor; `.vaultspec/CLI.md`.

### Phase `P02` - repair orchestration

Build the pipeline phases and make mutation order explicit.

- [x] `P02.S04` - implement preflight phase model; `src/vaultspec_core/vaultcore/checks`.
- [x] `P02.S05` - implement safe fix planning phase; `src/vaultspec_core/vaultcore/checks`.
- [x] `P02.S06` - rebuild graph state after mutation; `src/vaultspec_core/vaultcore/checks`.
- [x] `P02.S07` - emit postcheck phase result; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P03` - generated artifact lifecycle

Connect feature indexes to repair without treating them as user-authored docs.

- [x] `P03.S08` - add index refresh decision model; `src/vaultspec_core/vaultcore/index.py`.
- [x] `P03.S09` - add dry-run index reporting; `src/vaultspec_core/vaultcore/index.py`.
- [x] `P03.S10` - surface mandatory follow-up when index refresh is skipped; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P04` - Windows and path hardening

Handle case-only path operations and cross-platform Git risk explicitly.

- [x] `P04.S11` - detect case-only rename hazards; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P04.S12` - implement platform-aware two-hop rename path; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P04.S13` - report canonical path changes in JSON and human output; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P05` - output and root-cause grouping

Make recovery output operationally useful under pressure.

- [x] `P05.S14` - group diagnostics by root cause; `src/vaultspec_core/vaultcore/checks`.
- [x] `P05.S15` - classify mechanical, generated, and authorial work; `src/vaultspec_core/vaultcore/checks`.
- [x] `P05.S16` - add final delta report; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P06` - real-behavior tests

Lock the repair workflow with behavior tests that exercise actual filesystem,
graph, index, and CLI behavior.

- [x] `P06.S17` - test check order and INFO visibility; `src/vaultspec_core/tests/cli`.
- [x] `P06.S18` - test repair dry-run without mutation; `src/vaultspec_core/tests/cli`.
- [x] `P06.S19` - test index lifecycle after repair; `src/vaultspec_core/vaultcore/checks/tests`.
- [x] `P06.S20` - test case-only path behavior; `src/vaultspec_core/tests/cli`.
- [x] `P06.S21` - test operator wording contract; `src/vaultspec_core/tests/cli/test_cli_language_contract.py`.

### Phase `P07` - sync authority and UX hardening

Remove command-shape ambiguity by making top-level sync the only authoritative
complete synchronization surface and reframing narrower sync commands as
resource-scoped maintenance operations.

- [x] `P07.S22` - establish top-level sync authority in help and docs; `src/vaultspec_core/cli/root.py`.
- [x] `P07.S23` - deduplicate or reframe narrow sync surfaces; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P07.S24` - add post-add rule guidance; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P07.S25` - warn on stale provider-facing config after source mutations; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `P07.S26` - add end-to-end sync authority regression coverage; `src/vaultspec_core/tests/cli`.
