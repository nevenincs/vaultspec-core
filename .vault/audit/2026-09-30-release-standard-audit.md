---
tags:
  - '#audit'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:cfbc95c5572c26faf87c39699aaf00721982e94764e8e1370f3b6b2597c26327'
related:
  - "[[2026-09-30-release-standard-plan]]"
  - "[[2026-09-30-release-standard-adr]]"
---

# `release-standard` audit: `integrated review of the release standard across the vaultspec repositories`

## Scope

The plan-close review of the release standard as merged into vaultspec-core (#584),
vaultspec-rag (#568), vaultspec-a2a (#91), vaultspec-dashboard (#157, #159),
vaultspec-marketing (#14, #15) and devservers (#3), against every commitment in
`2026-09-30-release-standard-adr`: the proposal path, the dispatched cut, the draft
published last, dispatch-only lanes, no `workflows` credential, the trusted-author rule,
the untaggable-release diagnosis and runbook, token scopes, and each repository's
settings. An independent read-only reviewer read every merged diff and each repository's
`main`, and the live settings through the GitHub API. Findings resolved in the same
closeout are recorded with their resolution.

The review confirmed, in all five repositories: `skip-github-release` on the proposal and
`always-update`; `draft` and `force-tag-creation`; the candidate, gate and cut chain with
`--match-head-commit`, the behind-main refusal, the tree comparison, the tag check and the
diagnosis step; the proposal dispatching the merge gate last, which is the run whose
`Check: Merge gate (Linux)` satisfies the ruleset (the cut's called gate names its check
runs `<caller> / <called>` and satisfies nothing); read-only workflow defaults with writes
on the proposal and cut jobs only; no release credential beyond the workflow token; and
settings of a read-only token that cannot approve pull requests, selected and SHA-pinned
actions, outside-contributor approval, and release tags protected against update and
deletion.

## Findings

### core-acquisition-release-trigger | high | Core's acquisition lane still started from a release event

`.github/workflows/acquisition.yml` kept `on: release: types: [published]` while the
publication lane also dispatched it, so a release published with maintainer credentials -
the untaggable-release recovery - would start acquisition a second time outside the
dispatch chain. Resolved in this closeout: the trigger and its four event-tag reads are
removed, and the lane is dispatched by publication or runs on its weekly schedule.

### core-dispatch-only-guard-scope | high | Core's dispatch-only guard named two workflows instead of the tree

The release-authority guard asserted dispatch-only triggers over `publish.yml` and
`binaries.yml` only, which is why the finding above passed every gate. Resolved in this
closeout: `test_nothing_starts_from_a_tag_push_or_a_release_event` walks every workflow
and fails on a `release` trigger or a `push` on tags; restoring the acquisition trigger
fails it naming `acquisition.yml`.

### a2a-written-event-trust-guard | medium | a2a's trust guard never reached jobs started by comments, reviews or issues

`claude.yml` runs on the fleet with an OAuth token from `issue_comment`,
`pull_request_review_comment`, `pull_request_review` and `issues`, and its author checks
were correct, but the guard selected only workflows with a `pull_request` trigger.
Resolved in vaultspec-a2a#92: each such event a workflow listens to must name its own
author's association as the owner's or a collaborator's, and `MEMBER` is refused.

### dashboard-prerelease-hold | medium | Dashboard published the draft as a prerelease and promoted it later

The lane made the draft a public prerelease for acquisition and promoted it to `latest`
afterwards, so the release was visible half-finished. Resolved in
vaultspec-dashboard#160: the draft becomes the latest release in one step once every
build-side gate has passed, acquisition follows, the package-manager pointers wait for
acquisition, and the lanes guard refuses any prerelease edit.

### first-cut-unexercised | medium | No repository has yet released through a dispatched cut

By the maintainer's instruction the full CI lanes were not run for these changes, so the
cut, the draft publication and the refusal paths are proven by guards, local runs and
source reading, not by a release. Core's first new proposal run succeeded; a later one
failed in the fleet's runner-admission step before any of this code ran and was re-run.
Open until each repository's first release goes out through its cut.

### marketing-protection-unverifiable | medium | The private marketing repository has no ruleset to require the gate

On its plan, vaultspec-marketing exposes neither rulesets nor branch protection, so no
check is required and an ordinary merge could reach `main` unproven. The cut still
proves the exact head it merges before tagging it. Open.

### fleet-host-hardening | medium | The runner hosts remain persistent and shared

Runners are persistent rather than ephemeral, one OS account per host serves every
repository, and workspaces and caches survive between jobs; a fork's pull request runs
its own workflow copy, so only the outside-contributor approval and a runner-side check
can hold against it. These are host configuration in the private fleet repository, which
has in-flight work of its own, and are outside this plan. Open.

### dashboard-label-only-gate | low | Dashboard's pull requests run nothing until a user applies `ci:full`

Its merge gate starts only on the label, so even the owner's pull request reports no
checks until labelled. Stricter than the standard and safe; a maintainer moving between
repositories meets a different procedure. Recorded as a principled divergence.

### devserver-unsynced-consumers | low | Three non-vaultspec repositories still carry the untrusted dev-server workflow

The trusted-author clause landed at its source (devservers#3) and was re-synced into
vaultspec-dashboard and vaultspec-marketing. cadrumo-marketing, email-classification and
portfolio2026 pick it up on their next `just sync`. Open outside the vaultspec scope.

### rag-prerelease-tags-reach-pypi | low | Rag now uploads prerelease-named tags to PyPI as prereleases

Under the held-prerelease order a tag naming `rc`, `alpha`, `beta` or `dev` was never
promoted and never uploaded; under the draft order it publishes as a prerelease and
reaches the index, which pip ignores by default. Recorded behaviour change.

### diagnosis-tag-form | low | The diagnosis step derives the tag per repository

Core and rag compose `<package>-v<version>`; a2a, dashboard and marketing use
`v<version>`, matching their `include-component-in-tag: false`. Each form is the only one
that repository creates, and each is pinned by a guard. Recorded as a principled
divergence, as is dashboard dispatching its lane at the tag ref, which that lane
requires.

## Recommendations

- first-cut-unexercised: release each repository through its cut at its next release
  and watch the draft publication and the channel and acquisition dispatches; record the
  first run here.
- marketing-protection-unverifiable: either move marketing to a plan with rulesets and
  require `Check: Merge gate (Linux)`, or record in marketing's vault that the cut's
  proof is the only gate. Which of the two is a decision for that repository.
- fleet-host-hardening: a follow-on decision in the fleet repository on ephemeral or
  just-in-time runners, a job-started hook that refuses fork heads and untrusted authors
  on the runner itself, removing passwordless sudo, and separating release jobs from
  pull-request jobs and their caches.
- devserver-unsynced-consumers: run `just sync` from devservers for the three remaining
  consumers.
