---
tags:
  - '#plan'
  - '#doctor-dev-repo'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-04-30-doctor-dev-repo-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:6b43ff0d20973e19f7f33999b47a82ca2d806447012df0e9bb6ef7d2a0df1ba9'
---

# `doctor-dev-repo` plan

Fix `spec doctor` reporting a source dev repo as `CORRUPTED` for lacking an install-time manifest.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-04-30-doctor-dev-repo-self-review-exec`), which recorded completed
work but had no surviving plan to attribute it to. The Step below restates
what that record reports as done; it is closed on its evidence, not
re-executed. Authorization is historical: the work shipped fixing GitHub
issue #93.

Decision coverage: `[[2026-04-30-doctor-dev-repo-adr]]` governs the
multi-signal dev-repo detection this plan sequences.

## Steps

- [x] `S01` - detect a dev-repo workspace via a multi-signal check and return PRESENT instead of CORRUPTED; `src/vaultspec_core/core/diagnosis/collectors.py`.

## Parallelization

None. The Step is a single cohesive fix landed in one commit, and the work
is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs:
`pytest`, `ty check`, `ruff`, `vault check all`, and `spec doctor` all
reported clean, and the fix commit passed pre-commit and pre-push hooks
without `--no-verify`.
