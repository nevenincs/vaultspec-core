---
tags:
  - "#adr"
  - "#reference-publication-contract"
date: '2026-09-27'
related:
  - "[[2026-09-27-reference-publication-contract-audit]]"
  - "[[2026-09-09-reference-publication-contract-adr]]"
  - "[[2026-09-09-reference-publication-contract-reference]]"
  - "[[2026-09-18-release-publication-ordering-adr]]"
  - "[[2026-06-10-cli-reference-automation-adr]]"
supersedes:
  - '2026-09-09-reference-publication-contract-adr'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:27620661ccf680b57ae786c4fca20f3a7e52f305ba3959883f1940d138036c0a'
---

# `reference-publication-contract` adr: `published-release reference provenance` | (**status:** `accepted`)

## Problem Statement

The generated references attribute their surface against a version stamped from the
candidate's declared version on the release-please branch, before any release exists.
`2026-09-27-reference-publication-contract-audit` records the result: main's references
name `0.3.0`, a zero-asset draft, as the latest published release, while GitHub and PyPI
serve `0.2.6`. The rule this repository holds its documentation to is that every
reference is derived from the published GitHub release, and that a draft or prerelease
does not count. `2026-09-09-reference-publication-contract-adr` chose the candidate-branch
stamping that breaks it, so that choice is reversed here. The user authorized the
reversal on 2026-09-27.

## Considerations

- Under `2026-09-18-release-publication-ordering-adr` publication is the last act of
  `publish.yml`. A merged release pull request is not a release until then, and a stop
  before the flip is a normal, repairable state (`0.2.3`, `0.2.4`, `0.3.0`).
- GitHub's latest-release endpoint excludes drafts and prereleases by definition, which
  is exactly the membership the rule names.
- The published release carries its own wheel. Installed in isolation, that wheel emits
  its own surface through `spec reference snapshot --emit`: the surface a user installs,
  not a source tree's claim about it.
- The predecessor rejected tag derivation for shallow clones and for lacking an immutable
  object. Neither applies here: the release API needs no tag history, and the committed
  snapshot stays the offline record between recordings.
- Workflows resolve from main while recipes resolve from the tag being released, so a
  repair dispatch at an older tag runs today's workflow against yesterday's justfile.
- Every rendered copy is frozen - the wheel, the deployed `.vaultspec/` copy - so a
  present-tense "latest" expires in all of them.
- main is ruleset-protected; automation reaches it through a pull request, as the
  lockfile reconciliation in `.github/workflows/release-please.yml` already does.

## Considered options

- **Stamp the candidate's version on the release branch (status quo).** Rejected. It
  names a version as published whenever a release stops before publication, which is
  the audited failure.
- **Ask GitHub at render time.** Rejected. Rendering runs offline - pre-commit, inside a
  wheel - and a committed region still freezes whatever it rendered.
- **Record after publication from the tag's source tree.** Rejected. The source tree is a
  claim about the artifact; the wheel is the artifact.
- **Record after publication from the published wheel, land it by pull request, and guard
  main against GitHub's latest release.** Chosen.

## Constraints

- The snapshot's version and surface come only from the release GitHub reports as latest,
  never a draft or prerelease, and from that release's own attached wheel. Its version
  equals the version the release tag names. Nothing captures it from a source tree.
- The snapshot is written only through `spec reference snapshot --record`. The
  release-please branch never touches it.
- Rendered attribution names the release it was measured against and states that it was
  the latest published release when the reference was generated. It never asserts in
  the present tense which release is latest.
- A guard fails whenever the committed snapshot differs from what the latest published
  release's wheel emits. It is red between a publication and the merge of that
  publication's recording pull request; this replaces the predecessor's constraint that
  cutting a release may not turn a guard red.
- Workflow steps that run against a release tag keep working against tags cut before
  this decision.
- The publication job that holds `id-token: write` runs no project code.
- The `command-inventory` region's rendering is unchanged, per
  `2026-06-10-cli-reference-automation-adr`.
- GitHub is reached from development tooling only, never from the shipped CLI, and no
  dependency is added.

## Implementation

We will record the published surface after publication, from the published artifact.

A development-tooling reader resolves the latest release of the product's repository,
downloads the one wheel attached to it, installs it in isolation, and captures its
emitted surface. A recipe writes that document through `snapshot --record` and
re-renders the references. A new workflow runs the recipe on main and opens or updates a
pull request with the result; `publish.yml` dispatches it after publishing, and it can be
dispatched by hand for repair.

`release-please.yml` loses its surface refresh. In `publish.yml`, the pre-upload gate
compares the built wheel's emitted surface with the tagged tree's own, and the
post-attach read-back compares the downloaded asset byte for byte with the built wheel.
A repository guard derives the latest published surface the same way and fails when the
committed snapshot differs. The renderers say "Measured against `X`, the latest
published release when this reference was generated". The snapshot is then re-recorded
from the release that is latest today.

## Rationale

Only the published release can make "published" true. The knockout is the ordering:
while publication is the last step of the release lane, any stamp taken before it names
a version that may never publish, and `2026-09-27-reference-publication-contract-audit`
shows that it did. Reading the surface back from the published wheel derives the version
and the surface from the release itself rather than from a tree's claim about it. The
guard turns the one remaining gap, an unmerged recording pull request, from a silent
falsehood into a visible red.

## Consequences

- main's references name only released versions. A wheel's bundled reference is
  measured against the release before it and lists what that wheel added, which stays
  true after later releases.
- After each publication, the merge gate, main's daily health run, and `just ci` are red
  until the recording pull request merges. The workflow opens that pull request itself.
  A release cannot be cut while the snapshot lags, because `release.yml` runs the merge
  gate first.
- The repository lane now needs network access to GitHub and a wheel download. An
  outage or rate limit must read as an error distinct from a mismatch.
- Reconsider if GitHub's latest-release semantics change, or if releases stop carrying
  the wheel.
