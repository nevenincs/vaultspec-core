---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:7bdd5fab176dbbc57606dc316b57640f591bfe4a708b7633e5a1ff39397eabe7'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p1-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P5 plan: Coverage Matrix and Reporting

### Phase `P01` - Feature coverage reporting

Report per-feature document-type coverage, surfacing features missing plan, ADR, research, or index documents.

- [x] `P01.S01` - implement the feature coverage check reporting missing document types and stale feature indexes; `src/vaultspec_core/vaultcore/checks/features.py`.
- [x] `P01.S02` - register the feature coverage check and render its findings through the vault check CLI output; `src/vaultspec_core/cli/vault_check_cmd.py`.
- [x] `P01.S03` - add unit tests for the feature coverage check; `src/vaultspec_core/vaultcore/checks/tests/test_index_safety.py`.
