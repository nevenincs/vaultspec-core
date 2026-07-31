---
tags:
  - '#plan'
  - '#cli-ambiguous-states'
date: '2026-03-27'
modified: '2026-07-31'
body_hash: 'sha256:563c1364c82bec50fdb1d8cd867c4466dfea32812e52145ce6a9b47a3465a0ec'
tier: L2
related:
  - '[[2026-03-27-cli-ambiguous-states-resolver-adr]]'
  - '[[2026-03-27-cli-ambiguous-states-gitignore-adr]]'
  - '[[2026-03-27-cli-ambiguous-states-research]]'
  - '[[2026-03-27-cli-ambiguous-states-prior-art-research]]'
---

# `cli-ambiguous-states` implementation plan

## Steps

### Phase `P01` - Foundation

Introduce signal enums, manifest v2.0, and the gitignore managed-block module.

- [x] `P01.S01` - create the diagnosis package with signal enums and diagnosis dataclasses; `src/vaultspec_core/core/diagnosis/signals.py`.
- [x] `P01.S02` - upgrade the manifest to v2.0 with ManifestData and backward-compatible read/write wrappers; `src/vaultspec_core/core/manifest.py`.
- [x] `P01.S03` - add the gitignore managed-block module with marker handling and atomic writes; `src/vaultspec_core/core/gitignore.py`.
- [x] `P01.S04` - write phase 1 unit tests for signals, manifest v2.0, and gitignore block handling; `src/vaultspec_core/tests/cli/test_signals.py`.

### Phase `P02` - Signal collectors

Implement the collector functions that populate each diagnosis signal and the diagnose() orchestrator.

- [x] `P02.S05` - implement the framework, manifest, provider-dir, builtin-version, config, and gitignore signal collectors; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [x] `P02.S06` - implement the diagnose orchestrator that runs collectors in layered order with exception isolation; `src/vaultspec_core/core/diagnosis/diagnosis.py`.
- [x] `P02.S07` - write collector unit tests with parametrized degraded-workspace fixtures; `src/vaultspec_core/tests/cli/test_collectors.py`.

### Phase `P03` - Resolver engine and doctor command

Implement the resolution rule matrix and the doctor CLI command.

- [x] `P03.S08` - implement the resolver engine with the resolution rule matrix and dry-run support; `src/vaultspec_core/core/resolver.py`.
- [x] `P03.S09` - add the doctor CLI command with human-readable and JSON output and diagnosis-based exit codes; `src/vaultspec_core/cli/root_doctor.py`.
- [x] `P03.S10` - write resolver and doctor tests covering every rule and the human-readable and JSON output paths; `src/vaultspec_core/tests/cli/test_resolver.py`.

### Phase `P04` - CLI integration and command wiring

Wire the gitignore block, manifest v2.0 fields, and resolver preflight into install/sync/uninstall.

- [x] `P04.S11` - wire the gitignore managed block into install, sync, and uninstall flows; `src/vaultspec_core/cli/root_install.py`.
- [x] `P04.S12` - populate manifest v2.0 fields on install and sync; `src/vaultspec_core/cli/root_install.py`.
- [x] `P04.S13` - wire the resolver as a preflight check into the CLI command handlers; `src/vaultspec_core/cli/root_preflight.py`.
- [x] `P04.S14` - write integration tests for the 12 ambiguous-state scenarios using the degraded-workspace factory; `src/vaultspec_core/tests/cli/test_ambiguous_states.py`.
