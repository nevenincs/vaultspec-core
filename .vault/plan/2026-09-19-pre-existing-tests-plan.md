---
tags:
  - '#plan'
  - '#pre-existing-tests'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-05-01-pre-existing-tests-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:7db583948f77a5c4e93e02eb8cb8caec308b7fe0ad955ca87c4170edcd1b0fb7'
---

# `pre-existing-tests` plan

Fix two long-standing environmental test failures by removing a redundant test file and swapping a gemini probe.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-05-01-pre-existing-tests-self-review-exec`), which recorded
completed work but had no surviving plan to attribute it to. The Steps
below restate the two fixes that record reports as shipped; they are
closed on that evidence, not re-executed. Authorization is historical: the
work shipped closing GitHub issues #98 and #99.

Decision coverage: `[[2026-05-01-pre-existing-tests-adr]]` governs the fix
path chosen for each issue this plan sequences.

## Steps

- [x] `S01` - remove the redundant install-artifact test file superseded by test_mcps.py; `tests/test_mcp_config.py`.
- [x] `S02` - swap the gemini agent-load probe to --skip-trust skills list; `src/vaultspec_core/tests/cli/test_agents_render.py`.

## Parallelization

None. The two fixes are independent but landed together in one PR, and the
work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs: two
full-suite runs reported 1407 passed with 0 failures, plus clean `ty check`, `ruff`, `vault check all`, and `spec doctor` results, and an
empirical pre-flight confirming the new gemini probe reproduces the
original failure signature.
