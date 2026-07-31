---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:563bc3b6f44ea334f9687ba6cad1e7f2049a7577f5024c2d983863836d3a919c'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p1-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P3 plan: Chain Integrity Checks

### Phase `P01` - Chain integrity checks

Verify the exec to plan to ADR to research authoring chain via the schema and exec-mapping checks, wrapping existing grounding verification.

- [x] `P01.S01` - implement the schema check enforcing ADR-research grounding and plan-ADR linkage; `src/vaultspec_core/vaultcore/checks/references.py`.
- [x] `P01.S02` - implement the exec-to-plan mapping check verifying execution records map to a live Step; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.
- [x] `P01.S03` - register the schema and exec-mapping checks in the check registry; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P01.S04` - add unit tests for the exec-mapping chain check; `src/vaultspec_core/vaultcore/checks/tests/test_exec_mapping.py`.
