---
tags:
  - '#plan'
  - '#test-quality'
date: '2026-02-20'
tier: L1
related:
  - '[[2026-03-23-test-quality-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:a368ada65d30f80d89abcc6b49d6db69f5d9fdd40da387a6d44c84f047dd6b8b'
---

# `test-quality` plan

Audit the test suite for mocks, trivial skips, and private-state mutation that hide a missing production code path.

## Description

Reconstructed 2026-09-19 from this feature's historical execution records
(`2026-02-24-scout-alpha-report-exec`, `2026-02-24-scout-beta-report-exec`,
`2026-02-24-strict-audit-verdict-exec`), which are audit-shaped reports rather than
execution logs: two scout scans across the test tree and one strict-auditor verdict
adjudicating their findings against a no-mock, no-trivial-skip rule. The Steps below
restate what those records report as done; they are closed on that evidence, not
re-executed. The verdict found 103 of 117 audited test functions PASS and 14 FAIL
across 5 files, naming each file and the change it requires; no follow-on fix record
exists for this feature, so the remediation itself is out of this plan's evidence.
Authorization is historical: the audit ran in February 2026 under the test-quality bar
the ADR records.

Decision coverage: `2026-03-23-test-quality-adr` governs the real-production-code rule
this enforcement pass applies.

## Steps

- [x] `S01` - scan orchestration, protocol/a2a, protocol/acp, and subagent_server test suites for mock, skip, and private-mutation violations; `.vaultspec/lib/src/subagent_server/tests/test_mcp_tools.py`.
- [x] `S02` - scan CLI, e2e, RAG, core, vault, and hooks test suites for mock, skip, and private-mutation violations; `.vaultspec/lib/tests/cli/test_team_cli.py`.
- [x] `S03` - adjudicate the scout findings against the real-production-code rule and issue a strict verdict naming the files requiring changes; `.vaultspec/lib/tests/cli/test_team_cli.py`.

## Parallelization

None. The two scout scans could have run concurrently over disjoint directories, but
the verdict Step depends on both, and the work is complete, so no container is
available for concurrent assignment now.

## Verification

Verified historically by the execution records this plan reconstructs: scout-alpha
found 8 of 28 files with violations, scout-beta found 4 of 27 files with violations, and
the strict-auditor verdict scored 103 PASS / 14 FAIL across 117 audited test functions.
The paths sit under the pre-rename `.vaultspec/lib/` tree and are not re-checkable at
their original locators.
