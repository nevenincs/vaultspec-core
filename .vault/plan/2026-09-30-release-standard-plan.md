---
tags:
  - '#plan'
  - '#release-standard'
date: '2026-09-30'
tier: L2
related:
  - '[[2026-09-30-release-standard-adr]]'
modified: '2026-09-30'
body_schema: body-v2
body_hash: 'sha256:967d88c1023cbe4a4b2625a761083726686827c0ea4164d35694f8e7654762d8'
---

# `release-standard` plan

One release pipeline, and one trust boundary, across every vaultspec repository, led by
core.

## Description

Approved 2026-09-30. The maintainer authorized executing the release-standard model with
core leading, chose vaultspec-rag's dispatched cut with no new credential over a release
App, set the goal of one CI release pipeline across all vaultspec repositories, and
mandated that only trusted contributors can ever cause a job on the self-hosted fleet,
with the smallest token scopes and industry-standard hardening.

`2026-09-30-release-standard-adr` governs Phases P01 and P03: the dispatched cut, the
draft published last, dispatch-only lanes, and no credential that can write workflow
files. Its evidence is `2026-09-30-release-standard-research`. The draft-first order of
`2026-09-18-release-publication-ordering-adr` stands and is only re-timed.

Phase P02 applies the maintainer's trust mandate to core. It adds no costly decision of
its own: each Step tightens an existing control within the fleet contract core already
runs under, from the 2026-09-30 audit of all four public repositories' workflows and
settings. The audit found that a pull request's own workflow copy can edit away any
in-workflow guard, so the approval setting and a runner-side check are the controls that
hold against forks; the in-workflow rule still stops Dependabot and uncredentialled
same-repository authors, which the approval setting does not.

Out of this plan's scope and handed to the private fleet repository, where the runner
hosts are declared: ephemeral runners, a job-started hook that refuses fork heads and
untrusted authors on the runner itself, removing passwordless sudo, and separating
release jobs from pull-request jobs and their shared caches. Those change host
configuration, not these repositories, and that repository has in-flight work of its
own.

P03 Steps each land in their own repository and are recorded there as well; a P03 Step
closes here when its repository's branch carries the standard and its guards pass.

## Steps

### Phase `P01` - cut core's releases on dispatch

Core releases only through a maintainer-dispatched cut that proves, merges and tags within seconds, onto the draft that its lane publishes last.

- [x] `P01.S01` - record the evidence and the release-standard decision, amending the two release ADRs it changes; `.vault/adr/2026-09-30-release-standard-adr.md`.
- [x] `P01.S02` - split Release Please into a proposal path and a dispatched cut that proves, merges, tags and dispatches the binaries lane; `.github/workflows/release-please.yml`.
- [x] `P01.S03` - retire the post-tag relay whose proof the cut now makes before the tag; `.github/workflows/release.yml`.
- [x] `P01.S04` - pin the cut's authority and proof order in the release guards, each proven to fail; `dev/guards/test_automation_contracts.py`.
- [x] `P01.S05` - document the dispatched cut and the credentialed recovery for maintainers; `docs/README.md`.

### Phase `P02` - hold the fleet's trust boundary in core

Only trusted contributors can cause a job on the self-hosted fleet, with the smallest token scopes, and core's guards fail if that ever stops holding.

- [x] `P02.S10` - run a pull request's self-hosted jobs only for an owner or collaborator author or a collaborator's ci:full label, and fail the gate otherwise; `.github/workflows/merge-gate.yml`.
- [x] `P02.S11` - pin that trust rule over every job a pull request can reach, proven to fail; `dev/guards/test_ci_check_shape.py`.
- [x] `P02.S12` - move model-drift's write scopes from the workflow to the one job that writes; `.github/workflows/model-drift.yml`.
- [x] `P02.S13` - declare a read-only token default for main-health; `.github/workflows/main-health.yml`.
- [x] `P02.S14` - turn off token pull-request approval, require SHA-pinned actions, restrict the pypi environment to main, and drop the write deploy key's ruleset bypass once its use is confirmed; `GitHub settings: nevenincs/vaultspec-core`.

### Phase `P03` - converge every other vaultspec repository

vaultspec-rag, vaultspec-a2a, vaultspec-dashboard and vaultspec-marketing each adopt the same cut, draft and trust boundary in their own tree, recorded in their own vault.

- [x] `P03.S06` - move vaultspec-rag from its held prerelease to the draft and adopt the standard's guards; `vaultspec-rag: .github/workflows/release-please.yml`.
- [x] `P03.S07` - give vaultspec-a2a the dispatched cut and retire its tag-push trigger; `vaultspec-a2a: .github/workflows/release-please.yml`.
- [x] `P03.S08` - give vaultspec-dashboard the dispatched cut; `vaultspec-dashboard: .github/workflows/release-please.yml`.
- [x] `P03.S09` - give vaultspec-marketing the dispatched cut and a draft site release; `vaultspec-marketing: .github/workflows/release-please.yml`.

## Parallelization

P01 and P02 touch different files and may run in parallel. Core's P01 lands only after
vaultspec-rag's first dispatched cut has released successfully, because that run is the
first production exercise of the shape. Each P03 Step is independent of the others and
may run in parallel with them once P01 and P02 have settled the shape in core; each
works in its own repository's tree.

## Verification

- Each repository's guards fail if a release can be created outside the cut, if a
  workflow triggers on a tag push or a release event, or if the draft configuration is
  lost, and each such guard has been shown to fail on its mutation and pass on restore.
- Each repository's guards fail if a job a pull request can reach runs for an author who
  is neither the owner nor a collaborator without a collaborator's `ci:full`.
- Workflow lint, the fleet contract check, shellcheck of every changed `run:` block, and
  the full guard suite pass in each repository.
- One real release per repository goes out through a dispatched cut, as a draft
  published last, with no maintainer credential used.
- The final integrated review passes.
