---
tags:
  - '#audit'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:e3927d6c0b76bfac8dc5061518adafcc608919c21ef14c74caacd21c01b6f1b1'
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
