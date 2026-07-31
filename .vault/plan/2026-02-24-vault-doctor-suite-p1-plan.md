---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:7da1c039c15101919e070c00f626eb356e09b790d555d9c8bac4a896a2e69e31'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P1 plan: Foundation — Models, Registry, Safe Writer, CLI Scaffold, Remove `vault audit`

### Phase `P01` - Data models and check registry

Define the shared severity, diagnostic, and result data model that every vault health check writes against, and the registry that collects and runs them.

- [x] `P01.S01` - define Severity, CheckDiagnostic, and CheckResult as the shared data model for vault health checks; `src/vaultspec_core/vaultcore/checks/_base.py`.
- [x] `P01.S02` - implement the check registry that collects, filters, and runs registered vault health checks; `src/vaultspec_core/vaultcore/checks/__init__.py`.

### Phase `P02` - Safe writer and CLI wiring

Provide an atomic, dry-run-safe write helper for fixes, wire the doctor command into the CLI, and remove the superseded vault audit command.

- [x] `P02.S03` - implement an atomic, dry-run-aware write helper for check fixes; `src/vaultspec_core/core/helpers.py`.
- [x] `P02.S04` - wire the doctor command into the CLI and remove the vault audit command entirely; `src/vaultspec_core/cli/root_doctor.py`.

### Phase `P03` - Pre-commit integration and tests

Replace the legacy naming pre-commit hook with the doctor-backed entry and add unit tests for the registry, dry-run guard, and safe writer.

- [x] `P03.S05` - replace the check-naming pre-commit hook with the vault-doctor-backed entries; `.pre-commit-config.yaml`.
- [x] `P03.S06` - add unit tests for check registry dispatch, the dry-run guard, and the safe writer's no-write contract; `src/vaultspec_core/tests/cli/test_doctor.py`.
