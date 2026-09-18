---
tags:
  - '#adr'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:870cc7e017c848008355b55b9ad60a85ed23a4a266f6a802aa29972ad8318de0'
related:
  - "[[2026-09-18-release-publication-ordering-release-object-lifecycle-research]]"
  - "[[2026-03-22-clci-release-adr]]"
---

# `release-publication-ordering` adr: `a release is published only once it is complete` | (**status:** `accepted`)

## Problem Statement

This project's release object comes into existence before anything that gives it value.
`2026-09-18-release-publication-ordering-release-object-lifecycle-research` records the
sequence and its cost: release-please creates the tag and the public release when the
release pull request merges, and every artifact is attached to it afterwards by two
workflows that can fail. `vaultspec-core-v0.2.2` is what that looks like when it does -
a published release, sealed immutable, carrying nothing.

The ordering decides what kind of failure a release failure is. Published first, an
incomplete release is a live defect that must be detected, demoted, repaired and
promoted; the repair machinery that does this is a standing cost the pipeline pays on
every release to survive the few that go wrong. Published last, the same failure is an
absence - nothing was advertised, so nothing needs retracting.

`2026-03-22-clci-release-adr` chose release-please and settled that it creates the
GitHub release on merge. That choice is not being revisited: release-please stays, and so
does its ownership of the version, the tag, and the changelog. What this record settles
is when the release it creates becomes visible, which that ADR had no reason to consider
when binaries, attestations and channel pointers did not yet exist.

## Considerations

- A release carries steps of unequal reversibility. A PyPI version is spent permanently;
  a tag is permanent by ruleset here; a GitHub release can be deleted. The order must
  run from reversible to irreversible, not from cheap to expensive.
- GitHub documents draft-first as the recommended sequence under immutable releases, and
  immutability binds at publication rather than creation - both in
  `2026-09-18-release-publication-ordering-release-object-lifecycle-research`.
- `release-please@17.3.0`, the version already pinned here, can hold the release as a
  draft and still create the tag the lane builds from. The capability needs no upgrade
  and no new dependency.
- The publication and binary lanes must remain the top-level workflow of their own runs,
  or the PyPI trusted-publisher grant and the attestation signer pin both break.
- Commit `37572cb6` already ordered PyPI behind the binaries. It removed the race between
  the two lanes; it did not change when the release object appears.

## Considered options

- **Draft until proven, then publish (chosen).** release-please creates the release as a
  draft with the tag forced into existence; the lanes attach to the draft; the gate that
  already judges asset completeness publishes it. Costs one configuration change and one
  step; keeps release-please's tag and notes; matches GitHub's documented remedy.
- **Keep publishing first and repair afterwards (rejected).** The status quo. Works, and
  has worked, but pays for every release with machinery that exists only for the failing
  ones, and cannot hold under immutable releases, which forbid attaching assets after
  publication.
- **`skip-github-release` and a lane-owned release (rejected).** Reaches the same
  ordering, but release-please's own schema says it requires existing tagging
  infrastructure, which this repository would then have to build and maintain, and the
  changelog body configured in `release-please-config.json` would have to be
  reconstructed. Kept in reserve if drafts prove unworkable.
- **Channel pointers appended to the publication lane (rejected).** The smallest way
  to put the pointers after the publication, and the reason it loses is credentials:
  that job holds `id-token: write` for PyPI, which mints an OIDC token for any audience
  a step names, and the channel deploy key has no business beside it. The binaries
  workflow already separated those two capabilities deliberately.
- **Channel pointers in a lane of their own (chosen).** Dispatched by the publication
  lane after the flip, holding the deploy key and nothing else. Costs one file and one
  dispatch, and keeps the separation the binaries workflow paid for.
- **Publish as a prerelease and promote when complete (rejected).** The current
  behaviour of the repair path, proposed as the primary mechanism. A prerelease is
  published: it is visible, it is sealed under immutability, and it advertises an
  incomplete release rather than withholding it.

## Constraints

- Draft behaviour is load-bearing and only schema-verified, not yet exercised here; the
  research names `gh release download`, `gh release view`, `actions/attest` and the
  acquisition check against a draft as the open mechanical questions.
- Immutable releases is a repository setting, not a property of this repository's code.
  This decision is what makes enabling it safe; it does not itself enable it.
- The `protect-release-tags` ruleset forbids deleting or moving a release tag, so a tag
  created for a release that then fails to publish is permanent. That is accepted: a
  spent tag is cheap, and re-dispatching the lane reuses it.

## Implementation

release-please gains `draft` and `force-tag-creation`, so a merged release pull request
produces a tag and an unpublished release rather than a public one. Nothing downstream
changes shape: every job still checks out the tag for its source, and both consumer
workflows stay dispatched rather than called.

The lanes attach to the draft exactly as they attach today. The release-proven gate in
the binaries workflow keeps its existing judgment - every declared target present, its
release job green - and hands the draft to the publication lane. Publishing is that
lane's last act rather than the gate's, because the wheel and sdist are attached there:
a release published by the gate could never receive them.

Everything that ADVERTISES the release follows that publication, not merely the release
object itself. The acquisition check and the Scoop and Homebrew pointers both address a
release by its public URLs, so both run after the flip. The pointers move out of the
binaries lane into a lane of their own, dispatched once the release is public, which
also lets them be generated from the checksums read back off the published release
rather than from the build directory that produced them.

What the gate no longer needs is the path that demotes an incomplete release and
promotes a repaired one. An unpublished draft is invisible to `latest` by construction,
so the states that machinery managed cannot arise. It is removed rather than left
dormant, because dormant recovery code is indistinguishable from working recovery code
until the day it is needed.

The guards that encode the old ordering as a contract are updated to encode the new one,
including the negative form: the shapes this decision replaces are the ones worth
failing on if they return.

## Rationale

The knockout is that the alternative cannot hold under immutable releases at all.
GitHub forbids attaching assets to a published release once the setting is on, so
publish-then-attach is not a worse ordering there - it is a broken one. Draft-first is
not merely this project's preference; it is the sequence GitHub's own documentation
prescribes for the configuration this project wants to run.

Against the repair-based status quo the edge is that prevention retires machinery
instead of accumulating it. The demote-and-promote path is correct and was earned by
real incidents, but every line of it exists to manage a state that draft-first cannot
enter. Removing a correct mechanism is justified here precisely because its whole domain
disappears.

The reason to prefer drafts over `skip-github-release` is narrower and purely practical:
`release-please@17.3.0` already does tags and notes correctly, and the draft option was
added upstream for this exact combination. Taking the other route would mean
reimplementing two things that work in order to change the timing of a third.

## Consequences

The release object becomes truthful by construction: if it is visible, it is complete.
Immutable releases becomes safe to enable, and worth enabling - a release that only ever
appears finished is what the setting is for. A failed release leaves a tag and a draft
rather than a public artifact, and the repair is a re-dispatch of the same tag.

The cost is that the draft path is now load-bearing on first use, and the research names
the mechanics it has not proved: whether the attach, download, attestation and
verification steps see a draft the way they see a published release. A failure there is
discovered on a real release, and the mitigation is that it fails closed - an
unpublished draft is the safe state, not a shipped defect.

The pointer lane is a file and a dispatch where there used to be three steps, and it
can fail on its own: a release can be published and complete while its package-manager
pointers still name the previous version. That lag is visible, repairable by
re-dispatching the lane for the same tag, and strictly better than the alternative it
replaces, which was a pointer naming a version nobody could download.

Two further edges stay open. A tag is created before the release that justifies it, so a
release that never publishes leaves a permanent tag behind; the alternative, deferring
the tag, would deny every job the immutable ref it builds from. And the acquisition
check cannot see a draft, so its dispatch stays behind publication rather than in front
of it - the release is proved by the gate's own asset and provenance checks, not by that
lane.
