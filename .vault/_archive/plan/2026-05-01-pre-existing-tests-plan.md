---
tags:
  - '#plan'
  - '#pre-existing-tests'
date: '2026-05-01'
modified: '2026-07-31'
body_hash: 'sha256:90d5029cf7f9f36ac723ff2eecc2e751b852b2bb87ae42066e1445f55015ce3a'
tier: L2
related:
  - '[[2026-05-01-pre-existing-tests-adr]]'
  - '[[2026-05-01-pre-existing-tests-research]]'
---

# `pre-existing-tests` plan: pre-existing test failures (#98, #99)

## Steps

### Phase `P01` - fix pre-existing test failures

Repair the two pre-existing test failures recorded in #98 and #99.

- [x] `P01.S01` - delete the redundant mcp-config test module, keeping coverage in test_mcps.py (fixes #98); `src/vaultspec_core/core/tests/test_mcps.py`.
- [x] `P01.S02` - swap the gemini probe invocation to skills list and drop the unused probe-prompt constant (fixes #99); `src/vaultspec_core/tests/cli/test_agents_render.py`.
- [ ] `P01.S03` - run quality gates twice and sweep for skips, xfails, and similar source-repo path assertions; `src/vaultspec_core`.
