---
tags:
  - '#plan'
  - '#clci-release'
date: '2026-03-22'
tier: L1
related:
  - '[[2026-03-22-clci-release-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:3cad651ad3c584267ecd7c65fd8357d1377e2b2ae73c82a957bfd017b15f3f09'
---

# `clci-release` plan

Stand up a uv-native release pipeline: release-please version management and OIDC publishing to PyPI.

## Description

Reconstructed 2026-09-19 from this feature's two historical execution records
(`2026-03-22-clci-release-phase1-implementation-exec` and
`2026-03-22-clci-release-phase1-summary-exec`), which recorded completed work
but had no surviving plan to attribute it to. The Steps below restate what
those records report as done; they are closed on that evidence, not
re-executed. S02 derives from the summary record's Files Modified list, which
names the `ci.yml` actionlint pin that the implementation record does not
list; the summary attributes it to a security review's HIGH findings.
Authorization is historical: the work is governed by the accepted
`2026-03-22-clci-release-adr`, which this plan links in `related:`.

Decision coverage: the governing decision is `2026-03-22-clci-release-adr`
(accepted), which records the three-workflow release-please plus uv-publish
architecture this plan's Steps implement.

## Steps

- [x] `S01` - implement the uv-native release pipeline: release-please config, workflows, and smoke test; `release-please-config.json`.
- [x] `S02` - pin the ci workflow actionlint container tag per the security review; `.github/workflows/ci.yml`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report
them, and the work is complete, so no container is available for concurrent
assignment.

## Verification

Verified historically by the execution records this plan reconstructs:
actionlint clean on all three workflow files, the local smoke test's five
checks passing, ruff/ty clean, and remote CI green on all five jobs
(Workflow Lint, Lint/Type/Config/Link/Markdown, Tests, Vault Audit,
Dependency Audit) as the summary record reports.
