---
tags:
  - '#plan'
  - '#doctor-dev-repo'
date: '2026-04-30'
modified: '2026-07-31'
body_hash: 'sha256:e28eefcb75d6a237fde1597e71acfdcbd78b24035c74a2ff88222ee0fd0e7f6c'
tier: L2
related:
  - '[[2026-04-30-doctor-dev-repo-adr]]'
  - '[[2026-04-30-doctor-dev-repo-research]]'
---

# `doctor-dev-repo` `fix collect_framework_presence dev-repo handling` plan

### Phase `P01` - fix dev-repo false-positive in doctor

Stop spec doctor from false-positiving on the vaultspec-core source repository by teaching collect_framework_presence to recognize a legitimately unmanifested dev repo.

- [x] `P01.S01` - recognize a dev repo lacking a runtime manifest as adoptable instead of corrupted; `src/vaultspec_core/core/diagnosis/collectors_provider.py`.
- [x] `P01.S02` - add adoptable-signal and near-miss consumer test coverage for collect_framework_presence; `src/vaultspec_core/tests/cli/test_adoption.py`.
- [ ] `P01.S03` - confirm quality gates pass clean on this repo after the fix; `src/vaultspec_core`.
