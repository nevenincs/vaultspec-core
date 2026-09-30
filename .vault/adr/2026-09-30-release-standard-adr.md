---
tags:
  - '#adr'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:f5f9afd73b490de37ad27fb41c0d968c29586c71165b044de08a5bbd74db5cf6'
related:
  - "[[2026-09-30-release-standard-research]]"
  - "[[2026-09-18-release-publication-ordering-adr]]"
  - "[[2026-03-22-clci-release-adr]]"
---

# `release-standard` adr: `every vaultspec release is cut by dispatch and tagged within seconds of its merge` | (**status:** `accepted`)

## Problem Statement

A vaultspec release is tagged by the workflow token when Release Please next runs after
the release pull request merges. That token cannot create a tag or release for a commit
whose workflow files differ from main's head, so any workflow change that lands while
the release run waits for a fleet runner strands the release: no rerun can finish it.
vaultspec-rag 0.5.3 stalled exactly this way, and every vaultspec repository shares the
exposure (`2026-09-30-release-standard-research`).

The five repositories have also drifted into five release shapes, so a maintainer meets
a different procedure, a different release object and a different failure in each.
vaultspec-rag has already moved to a dispatched cut; without a standard the others keep
diverging from it and from each other.

The maintainer authorized this standard on 2026-09-30: releases converge on
vaultspec-rag's dispatched cut with no new credential, core leads, and the goal is one
release pipeline across all vaultspec repositories.

## Considerations

- The workflow token's tagging rule and the options that close the window are
  established in `2026-09-30-release-standard-research`.
- No credential that can write workflow files may be readable from jobs on the
  self-hosted fleet, and token scopes stay at the minimum (maintainer, 2026-09-30).
- Release Please owns the version, the tag and the changelog
  (`2026-03-22-clci-release-adr`).
- A release is published only once complete: a draft with a forced tag, flipped last
  (`2026-09-18-release-publication-ordering-adr`).
- The publication and binary lanes must stay the top-level workflow of their own runs,
  or the PyPI trusted publisher and the attestation signer pin break
  (`2026-09-18-release-publication-ordering-adr`).
- Every job runs on the self-hosted fleet (`dev/ci_contract.py`).
- The merge gate's ruleset has an admin bypass, so it cannot stop a change from
  landing.

## Considered options

- **A dispatched cut that proves, merges and tags in one job (chosen).** Closes the
  window to seconds with the workflow token and proves the tree before any tag exists.
  Leaves a hand-merged proposal and those seconds uncovered.
- **The release job on a hosted runner (rejected).** Shortens the wait without a
  credential, but breaks the fleet contract and leaves the same residual window.
- **A GitHub App with `workflows` write (rejected).** The only complete fix, but its
  key could rewrite workflow files from any job that can read it on the self-hosted
  fleet, and the tags and releases it creates wake tag- and release-triggered
  workflows. The maintainer chose against it on 2026-09-30.
- **Refusing workflow changes while a release awaits its tag (rejected).** An admin
  merge bypasses the gate; the change that stalled 0.5.3 merged 31 seconds after its
  gate run was queued.
- **Keeping release-on-merge with a runbook (rejected).** Leaves the window as long as
  the fleet's queue.

## Constraints

- Scope: vaultspec-core, vaultspec-rag, vaultspec-a2a, vaultspec-dashboard and
  vaultspec-marketing. Core is the lead implementation; each other repository converges
  in its own tree and records its adoption in its own vault.
- Release Please never creates a release outside the cut. Its proposal path runs with
  `skip-github-release` and `always-update`, is started only by main's own commits in
  the same repository, and never merges, tags or publishes. When a repository refreshes
  the proposal is its own choice: the cut's proof, not the refresh, is what a release
  rests on.
- A release is created only by a maintainer-dispatched cut. The cut proves the
  proposal's exact head with the full merge gate and every accelerator or hardware tier
  the repository has, before any tag exists. It merges with `--match-head-commit`,
  refuses a merged tree that differs from the proven tree, and creates the tag and
  release in the same job immediately afterwards.
- The release object is a draft with a forced tag, published last by the publication
  lane. This applies to every repository; vaultspec-rag's published-and-held release
  converges on the draft.
- Every lane after the tag starts only by dispatch, or by a call from a dispatched run.
  No workflow triggers on a tag push or on a release event.
- No credential holding the `workflows` permission is created for releases. The cut
  runs on the workflow token, with write scopes granted only to the job that merges and
  tags.
- A proposal merged by hand is released by the next cut. When its workflow files have
  moved on since, the cut names the release it cannot tag and the repository's runbook
  finishes it with maintainer credentials.
- Tag forms stay as each repository has them; changing a tag form breaks installers.
- This amends `2026-03-22-clci-release-adr`, whose release is created when the Release
  PR merges, and `2026-09-18-release-publication-ordering-adr`, whose tag and draft are
  produced by the merge. Both now happen when a maintainer dispatches the cut; the draft
  and publication order stand unchanged.

## Implementation

We will give every vaultspec repository the same Release Please workflow shape: a
proposal path that follows main's green gate and never releases, and a dispatched cut
that proves the proposal, squash-merges it, checks the merged tree, has Release Please
create the tag and draft, and dispatches the repository's release lane. vaultspec-rag's
workflow at `9b0df9b3` is the reference shape. A step after release creation names a
release the workflow token cannot tag, and each repository's maintainer documentation
carries the credentialed recovery.

Hypotheses that may change within the constraints:

- In core, the cut proves the tree before the tag, so the post-tag proof in
  `release.yml` is expected to become redundant and be removed; the lane keeps its
  dispatch entry point.
- Guards in each repository fail if release creation appears outside the cut, if a
  workflow triggers on tags or releases, or if the draft configuration is lost. Whether
  these live in each repository or in the fleet's rendered contract is settled when
  the second repository adopts them.
- vaultspec-rag's 0.5.4 cut is the first production run of the shape; core lands after
  it succeeds.

## Rationale

The cut is the only option that closes the window without a new credential and without
leaving the fleet. The maintainer's security mandate removes the App, the admin bypass
removes a gate-based refusal, and the fleet contract removes the hosted runner. The cut
also proves the release tree before a tag exists, which matters here because release
tags cannot be deleted under the tag ruleset. One shape across every repository means
one operator procedure, dispatching the cut, and one recovery.

## Consequences

- Merging a release proposal no longer releases it. A maintainer dispatches the cut,
  the same way in every repository.
- A release takes the time of a full gate and its hardware tiers before the tag, and a
  failed proof leaves no tag behind.
- The window shrinks from the fleet's queue wait to the seconds between merge and tag
  inside one job. A hand-merged proposal can still be stranded; the diagnosis step and
  runbook cover it.
- vaultspec-rag gives up its visible prerelease for the draft; vaultspec-a2a gives up
  its tag-push trigger; vaultspec-marketing adopts drafts for its site releases.
- Reconsider if GitHub lets the workflow token hold `workflows`, or if the repositories
  move to an organisation whose environment-scoped App keys and ephemeral runners change
  the credential risk.
