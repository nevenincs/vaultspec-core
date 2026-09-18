---
tags:
  - '#plan'
  - '#release-publication-ordering'
date: '2026-09-18'
tier: L1
related:
  - '[[2026-09-18-release-publication-ordering-adr]]'
modified: '2026-09-18'
body_schema: body-v2
body_hash: 'sha256:e10e70843399bdebd41371ff5bbbd0d04e742a7e6b43f52d15787e06b34950eb'
---

# `release-publication-ordering` plan

Make the release object appear only once it is complete, and retire what existed to
repair it when it did not.

## Description

Approved 2026-09-18

Authorized in conversation: the decision in `2026-09-18-release-publication-ordering-adr`
was presented with its ordering, its two rejected alternatives, and the re-enabling of
immutable releases that follows it, and approved in reply with instruction to execute the
whole of it. That authorization covers the repository setting in `S04` and the release
repair in `S05`, both of which act on live GitHub state rather than on tracked files.

Decision coverage: `2026-09-18-release-publication-ordering-adr` governs every Step and
is the only ADR that does. It inherits its evidence from
`2026-09-18-release-publication-ordering-release-object-lifecycle-research`, which
carries the draft and tag mechanics, the GitHub documentation for immutable releases,
and the constraints that keep both consumer workflows dispatched rather than called.
`2026-03-22-clci-release-adr` remains accepted and unchanged. Release-please,
`uv publish`, and PyApp are not revisited here - only the moment at which the release
release-please creates becomes visible.

The work is the ordering change itself (`S01`, `S02`), the documentation that describes
the lane to maintainers (`S03`), and the two live actions the decision makes safe or
necessary (`S04`, `S05`). Commit `37572cb6` already put PyPI behind the binaries; this
plan does not revisit that chain, it publishes the draft from the same gate that
dispatches it.

## Steps

- [x] `S01` - Hold the release as a draft with a forced tag; `release-please-config.json, dev/guards/test_automation_contracts.py`.
- [x] `S02` - Publish the proven draft last and retire the prerelease holding path; `.github/workflows/binaries.yml, .github/workflows/publish.yml, dev/guards/test_automation_contracts.py`.
- [x] `S03` - Describe the release lane as it now runs; `docs/README.md`.
- [x] `S04` - Re-enable immutable releases on the repository; `GitHub repository setting, no tracked file`.
- [x] `S05` - Repair the empty v0.2.2 release; `GitHub release object, no tracked file`.

## Parallelization

Sequential. `S02` publishes what `S01` leaves unpublished, so the two are one change
split for review rather than independent work, and a tree carrying only `S01` would
create drafts nothing ever publishes. `S03` describes the result of both. `S04` must
follow `S02`, because enabling immutability before the release is created last would
reinstate the failure this plan removes. `S05` is last: it exercises the repaired lane
on a real tag, which is only meaningful once the lane is the new one.

No Step is assigned to a worker; this plan is executed in one ownership.

## Verification

- `just check-workflow` passes, covering `actionlint` and the CI contract.
- `uv run pytest dev/guards -m repo` passes, with the automation-contract guards
  asserting the new ordering in both directions - that the draft is configured and
  published by the proven gate, and that the demote-and-promote path and the parallel
  publication dispatch do not return.
- `vaultspec-core vault check all` and `vaultspec-core vault plan check` report clean.
- `GET /repos/nevenincs/vaultspec-core/immutable-releases` reports `enabled: true` after
  `S04`.
- The release for `vaultspec-core-v0.2.2` carries every declared target after `S05`, or
  the Step records why it could not and what was left.
- Final review under the vaultspec system section, covering the workflows, the guards,
  and the documentation together as one behaviour.
