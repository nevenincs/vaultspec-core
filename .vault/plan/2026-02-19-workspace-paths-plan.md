---
tags:
  - '#plan'
  - '#workspace-paths'
date: '2026-02-19'
tier: L1
related:
  - '[[2026-02-19-workspace-path-decoupling-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:df729230019e5c16096a4f12802c678332f9231d52f628793ba127169e6e6d95'
---

# `workspace-paths` plan

Decouple the framework's path resolution into a standalone workspace module supporting both standalone and explicit-content-dir deployment.

## Description

Reconstructed 2026-09-19 from this feature's surviving evidence
(`2026-02-19-workspace-paths-review-exec`), which is a code review record
rather than an execution log: it audits the nine files listed in its Scope
against `2026-02-19-workspace-paths-implementation-plan` and reports
Status `REVISION REQUIRED`, with three HIGH findings about `framework_root`
forwarding at the CLI call sites. No later execution record for this
feature survives, so the Steps below restate the files that review reports
as implemented; they are closed on that evidence, not re-executed, and the
HIGH findings are preserved here as historical fact rather than resolved.
The review named a plan stem, `2026-02-19-workspace-paths-implementation-plan`,
that was never scaffolded; that stale wiki-link has no matching document
and is left as an unresolved dangling reference in the review's frontmatter,
while this reconstructed plan is separately linked to the review record.

Decision coverage: `[[2026-02-19-workspace-path-decoupling-adr]]` governs
the resolution matrix, the layout and mode types, and the `--content-dir`
override this plan sequences.

## Steps

- [x] `S01` - add the core workspace resolution module with the layout and mode types; `.vaultspec/lib/src/core/workspace.py`.
- [x] `S02` - add the workspace resolution test suite covering all six matrix rows; `.vaultspec/lib/src/core/tests/test_workspace.py`.
- [x] `S03` - wire content_dir into the config registry and the two-step bootstrap; `.vaultspec/lib/src/core/config.py`.
- [x] `S04` - wire --content-dir through the CLI, subagent, and vault entry points; `.vaultspec/lib/scripts/cli.py`.
- [x] `S05` - add the companion extension manifest and align requirements.txt; `extension.toml`.

## Parallelization

None. The review covers one implementation as a single reviewed change
set, and the work is complete, so no container is available for
concurrent assignment.

## Verification

Verified historically by the review record this plan reconstructs: all six
resolution-matrix rows and eight ADR deliverables are checked PASS or PASS
with a caveat, against the three call-site HIGH findings the review
flagged as required before merge.
