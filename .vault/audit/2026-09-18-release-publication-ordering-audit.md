---
tags:
  - '#audit'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:16d56fc7f8d9e6465c36f9002c3bb0bab74860094db707a282b39e2fe4643d25'
related:
  - '[[2026-09-18-release-publication-ordering-plan]]'
---

# `release-publication-ordering` audit: `draft-first release lane`

## Scope

Plan close for `2026-09-18-release-publication-ordering-plan`, Steps `S01` through
`S05`, reviewed as one behaviour rather than five diffs: a release travelling from a
merged release pull request to a published GitHub release, PyPI, and the package
managers. The files are `release-please-config.json`, `.github/workflows/binaries.yml`,
`.github/workflows/publish.yml`, `docs/README.md`, the two guard modules, and the
repository's immutable-releases setting.

Traced against `2026-09-18-release-publication-ordering-adr`: the release object is
created unpublished, every lane attaches to that draft, and publication is the last
reversible act before nothing remains to reverse.

## Findings

### channel-pointers | high | The Scoop manifest and Homebrew formula are pushed while the release is still a draft, so both advertise download URLs that 404 until the publication lane finishes

The binaries lane generates the two package-manager pointers from the checksums it just
built and commits them to the shared channel root, at `.github/workflows/binaries.yml`
in the `release` job, before its gate hands the draft on. Those pointers address assets
by release download URL - `dev/packaging/products.py:110` and `dev/packaging/scoop.py:45`
both build `{homepage}/releases/download/{tag}/...` - and a draft release serves none of
them.

Publication now happens at the end of `publish.yml`, so between the pointer commit and
the flip there is a window, the length of a wheel build, a smoke test, a PyPI upload and
two verifications, in which `brew upgrade` or `scoop update` resolves this version and
fails to download it. The window did not exist before this plan: the release was
published from the moment release-please created it, so by the time pointers were pushed
its assets were live.

`dev/packaging/validate.py` cannot catch this. It checks that a manifest is structurally
coherent and that its digests match, and never fetches a URL, so a pointer to a
not-yet-served asset validates exactly as well as one to a live asset.

This is the one place where the plan's own principle - nothing advertises a release
before it is published - was applied to the release object and not to the things that
point at it.

### pypi-before-publication | low | A failed publication leaves PyPI carrying a version whose GitHub release is still a draft

`publish.yml` uploads to PyPI and then takes the release out of draft, so a failure
between the two leaves the index carrying a version that the releases page does not
show. This is the designed trade and the better of the two orders - the alternative
advertises a release whose PyPI version may never arrive - and it is repairable, since
`uv publish --check-url` makes a re-dispatch a no-op on the already-uploaded files.
Recorded because the asymmetry is deliberate and should not be read later as an
oversight.

### recreated-release-state | low | The idempotent release guard now creates a draft, which is only correct while publication stays in the same job

`publish.yml`'s "Ensure the GitHub Release exists" passes `--draft` so a repair dispatch
recreates the release in the state release-please would have left it in. That is right
today because the same job publishes it a few steps later. If publication ever moves out
of this job, this guard becomes a way to create a release nothing ever publishes.

### draft-visibility | low | Draft handling was measured rather than assumed, and the measurement should be re-run if the lane's `gh` usage changes

Every release operation the two lanes perform was exercised against a real draft before
the change, recorded in
`2026-09-18-release-publication-ordering-release-object-lifecycle-research`. The result
holds for `upload`, `view --json assets`, `download --pattern` and `edit --draft=false`;
it says nothing about operations the lanes do not currently use.

### channel-pointers-resolved | high | Resolved by moving the pointers to their own lane, dispatched after publication

Re-reviewed after the fix. The pointers are generated and pushed by
`.github/workflows/channels.yml`, dispatched by `publish.yml` after the step that takes
the release out of draft, so the advertisement can no longer precede the thing it
advertises. The binaries lane no longer holds `CHANNEL_ROOT_DEPLOY_KEY`, no longer runs
`dev/packaging` code, and is reduced to attaching assets and proving them.

The decision the recommendation asked for was taken rather than deferred: the key lives
in a lane of its own, not beside the `id-token: write` grant in the publication job. The
reasoning is the same one `binaries.yml` already recorded when attestation moved into a
job holding no key - `id-token` mints a token for any audience a step names, so a job
holding both is the widest surface in the repository.

Two properties were added that the original arrangement did not have. The pointers are
generated from the `SHA256SUMS` read back off the published release rather than from the
build directory that produced it, so they describe what a user downloads rather than
what the upload was assumed to have delivered. And the lane refuses to run against a
draft, which matters because it is now dispatched by another workflow: a dispatch aimed
at an unpublished release is the one mistake that reinstates the defect.

Guarded in both directions - the binaries lane may not generate pointers or hold the
key, the channels lane must check for a draft before it writes, the dispatch must follow
the publication, and no job in any workflow may hold the deploy key and a token grant at
once.

### adr-drift | low | The ADR described the gate publishing the draft, which execution corrected

The decision record said the release-proven gate would publish the draft. It cannot: the
distribution is attached by the publication lane, so a release published by the gate
could never receive it. Corrected in the ADR when the pointer decision was appended.
Recorded because the correction came from execution rather than from review, and the
record was wrong in the interval.

### release-0-2-3-blocked | low | The first release through the new lane is stuck on an offline runner, not on this work

`vaultspec-core-v0.2.3` merged while this fix was being written. Its tag and draft
release were created correctly - the first live proof that `draft` and
`force-tag-creation` behave as the research measured - but `Core Binaries` was cancelled
after preflight refused the build: `[self-hosted,macos,arm64]` matched one runner with
none online, the power-gated host on battery. No binaries were built, no pointers were
pushed, and nothing reached PyPI. The release needs a re-dispatch with that host on AC,
or with `allow_queue`. Recorded so the empty draft is not later read as a defect of the
ordering.

## Recommendations

Resolve the channel-pointer finding before the next release reaches a package manager.
Everything that advertises a release has to follow its publication, which is the rule
the acquisition-check dispatch already moved for; the pointers are the same kind of
thing and are still on the wrong side of it. The straightforward form is to move
generation, validation and the channel-root commit to the end of `publish.yml`, after
the release is published.

That move is not merely mechanical, and it names a decision a follow-on ADR must make:
whether `CHANNEL_ROOT_DEPLOY_KEY` may live in the job that holds `id-token: write` for
PyPI trusted publishing. `binaries.yml` deliberately separates those two grants today -
its `release` job carries the deploy key and no OIDC token, and its `attest` job carries
the token and no key - so co-locating them in `publish.yml` reverses a standing
separation. The alternative is a third lane, dispatched after publication, that holds
the key alone.

Leave the two `low` findings recorded. The first two describe intended behaviour with a
condition attached, and the third is a scope statement about the evidence.

**REVISION REQUIRED** - one `high` finding. `S02` is the affected Step; the fix needs
authorization for the secret-placement decision before it can be executed.

**PASS** on re-review, after the channel-pointer finding was resolved in `S02` and the
secret placement was authorized. No critical or high findings remain open. The three
`low` findings from the first pass and the three added on re-review are recorded and
need no action beyond being read; `release-0-2-3-blocked` names a live release waiting
on a runner, not on this repository.
