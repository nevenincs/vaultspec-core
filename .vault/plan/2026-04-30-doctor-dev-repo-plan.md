---
tags:
  - '#plan'
  - '#doctor-dev-repo'
date: '2026-04-30'
modified: '2026-07-31'
body_hash: 'sha256:63e551b4cde5758122f6eac5ab3ef074aed8175103d466d67b4d02d49ccc1c67'
tier: L2
related:
  - '[[2026-04-30-doctor-dev-repo-adr]]'
  - '[[2026-04-30-doctor-dev-repo-research]]'
---

# `doctor-dev-repo` `fix collect_framework_presence dev-repo handling` plan

## Steps

### Phase `P01` - fix dev-repo false-positive in doctor

Stop spec doctor from false-positiving on the vaultspec-core source repository by teaching collect_framework_presence to recognize a legitimately unmanifested dev repo.

- [x] `P01.S01` - recognize a dev repo lacking a runtime manifest as adoptable instead of corrupted; `src/vaultspec_core/core/diagnosis/collectors_provider.py`.
- [x] `P01.S02` - add adoptable-signal and near-miss consumer test coverage for collect_framework_presence; `src/vaultspec_core/tests/cli/test_adoption.py`.
- [ ] `P01.S03` - confirm quality gates pass clean on this repo after the fix; `src/vaultspec_core`.
