---
tags:
  - '#plan'
  - '#marketing-and-documentation'
date: '2026-02-20'
tier: L1
related:
  - '[[2026-02-20-marketing-and-documentation-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:7d654ca3aba0066dfd80d822f130e3d078931583947372a23c6757d3f41cba1c'
---

# `marketing-and-documentation` plan

Retire the root `docs/` tree and move operational documentation into `.vaultspec/docs/`.

## Description

Reconstructed 2026-09-19 from this feature's six historical execution records
(`2026-02-20-marketing-and-documentation-p1-step1-exec` through `-step4-exec`,
the `-p1-review-exec` code review, and the `-p1-summary-exec` rollup), which
recorded completed work but had no surviving plan to attribute it to. The
Steps below restate what those records report as done; they are closed on
that evidence, not re-executed. S05 derives from the review record
(`-p1-review-exec`), which found one MEDIUM and one LOW finding and reports
both fixed inline before it passed. Authorization is historical: the work is
governed by the accepted `2026-02-20-marketing-and-documentation-adr`, which
this plan links in `related:`.

Decision coverage: the governing decision is
`2026-02-20-marketing-and-documentation-adr` (accepted), which records the
restructure from a root `docs/` folder to `.vaultspec/docs/` sub-chapters
that this plan's Steps implement.

## Steps

- [x] `S01` - create the .vaultspec/docs sub-chapters consolidating operational documentation; `.vaultspec/docs/concepts.md`.
- [x] `S02` - retire the root docs directory tree; `docs/`.
- [x] `S03` - rewrite the root README with an expanded quick start and worked example; `README.md`.
- [x] `S04` - add a documentation navigation section to the vaultspec README; `.vaultspec/README.md`.
- [x] `S05` - apply the code review fixes for the stale docs references; `README.md`.

## Parallelization

None. The Steps are recorded sequentially as the historical phase records
report them, and the work is complete, so no container is available for
concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: the
code review recorded in `-p1-review-exec` found no critical or high issues,
confirmed all five plan intent decisions implemented, and reports a final
PASS status after its two recommended fixes were applied.
