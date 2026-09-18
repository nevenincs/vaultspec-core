---
tags:
  - '#research'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:bcc203198c907573a5447607b01f97665f9a0f6a9aed6f25b5f4eadb4e03f624'
related: []
---

# `release-publication-ordering` research: `release-object-lifecycle`

A release of this project is assembled by four workflows that publish into a GitHub
release object release-please has already created, and the question is whether that
object should exist before its contents do. It matters because the release is the only
artifact a user acquires by, and because two of the steps behind it - a PyPI version and
a git tag - cannot be taken back once taken. The evidence says the object should be
created as a draft and published last: GitHub documents exactly that sequence for
repositories with immutable releases, and `release-please@17.3.0` carries the two
configuration options that make it reachable without giving up release-please's
ownership of the tag or the notes. The alternative that avoids drafts,
`skip-github-release`, requires this repository to build tagging infrastructure it does
not have.

## Findings

### The release object is created before anything that fills it exists

`release-please-action` creates the tag and the GitHub release when the release pull
request merges, and `.github/workflows/release-please.yml:170-177` then dispatches
`release.yml` with that tag. Everything that gives the release value - the wheel, the
sdist, the per-target bundles, `SHA256SUMS`, the attestations - is attached afterwards by
`publish.yml` and `binaries.yml`. The window between the two is not theoretical:
`vaultspec-core-v0.2.2` exists as a tag and a public release carrying zero assets, and
release `391505545` reports `"immutable": true` with an empty asset list.

### Publication was ordered so that the irreversible step could not be protected

`release.yml` dispatched `publish.yml` and `binaries.yml` with two `gh workflow run`
calls in one step. A dispatch starts a run and returns, so neither lane could observe
the other, and PyPI - where a version number is spent permanently on first upload - ran
beside the binary matrix that is the most likely thing in the release to fail. Commit
`37572cb6` chained them, which removes the race but not the cause: the release object
still predates its contents, so a failure is still repaired rather than prevented.

### The repair machinery exists only because the release goes public early

`.github/workflows/binaries.yml:1480-1611` demotes an incomplete release to a prerelease,
reports what is missing, and promotes it back when a re-dispatch completes the matrix.
Roughly 130 lines, correct for what it does, and entirely a consequence of the ordering:
a release object that never appeared incomplete would need none of it.

### GitHub documents draft-first as the remedy, in terms

`github/docs`, `content/repositories/releasing-projects-on-github/managing-releases-in-a-repository.md:37`:
"If you have enabled immutable releases for your repository, it's recommended to create
releases as drafts first, attach all assets, and then publish. This ensures all assets
are in place before the release becomes immutable." The same file at line 84 states what
the seal covers: "you cannot add, replace, or delete assets after a release is
published, and you cannot move or delete its tag while the release exists. You can still
edit the title and release notes, and change whether the release is a pre-release or the
latest release."

Two consequences follow. Immutability binds at publication, not at creation, so a draft
is a genuine staging area rather than a sealed object with a flag. And the prerelease
and latest markers remain writable after the seal, so the demotion path above survives
immutability even though asset attachment does not.

### Immutable releases are a repository setting, readable and writable over REST

`GET /repos/{owner}/{repo}/immutable-releases` returns
`{"enabled":..., "enforced_by_owner":...}` and `DELETE` on the same path disables it; the
field appears in neither the repository object nor the GraphQL `Repository` type, and
`PATCH /repos/{owner}/{repo}` silently ignores an `immutable_releases` key. The setting
was enabled on this repository and `enforced_by_owner` was false, so it was a local
choice rather than an organization policy.

### release-please can hold the release as a draft and still create the tag

`release-please@17.3.0` - the version `release-please-action@4.4.1` depends on, pinned at
`5c625bfb5d1ff62eadeeb3772007f7f66fdcf071` - defines both options in
`schemas/config.json`. `draft`: "Create the GitHub release in draft mode." And
`force-tag-creation`: "Force the creation of a Git tag for the release. This is
particularly useful when `draft` is enabled, because GitHub does not create a Git tag for
draft releases until they are published."

That second description names the obstacle and removes it. A draft release does not
create its tag, and every job in this pipeline checks out the tag for its source, so
`draft` alone would strand the lane with nothing to build. `force-tag-creation` restores
the tag while leaving the release unpublished, which is the combination the sequence
needs. The GitHub-side behaviour both options address is measured below; what remains
unexercised is release-please's own handling of them, for which the evidence is the
schema of the pinned version and the upstream feature request
`googleapis/release-please#2627`.

### `skip-github-release` reaches the same ordering at a higher price

The same schema documents `skip-github-release` as "Skip tagging GitHub releases for this
package. Release-Please still requires releases to be tagged, so this option should only
be used if you have existing infrastructure to tag these releases." Taking it means this
repository owns tag creation and release-note generation for itself, duplicating what
release-please already does correctly, and it discards the changelog body that
`release-please-config.json` is configured to shape. It is the option to choose only if
drafts prove unworkable.

### PyPI ordering is already safe against repeat dispatches

`publish.yml:215` runs `uv publish --check-url https://pypi.org/simple/ dist/*`, which
skips files the index already carries. Re-dispatching a publication for a version already
on PyPI is a no-op rather than a duplicate-upload failure, so the publication may sit at
the end of a chain that is re-run to repair the binaries.

### Two constraints bound any restructuring of the lanes

PyPI trusted publishing matches the top-level workflow of the run, and
`publish.yml:281-285` verifies attestations with
`--signer-workflow "$GITHUB_REPOSITORY/.github/workflows/publish.yml"`. Converting either
consumer into a `workflow_call` target would make the caller the top-level workflow and
break the trusted-publisher grant and the signer pin together, which is why
`release.yml:16-21` records that they are dispatched rather than called. Any new sequence
has to keep both files as the top-level workflow of their own runs.

### Every `gh` operation the lanes use works against a draft

Measured against this repository on 2026-09-18 with a throwaway draft, since the answer
decides whether the sequence is reachable at all. `gh release upload`, `gh release view --json assets`, and `gh release download --pattern` all succeeded against an unpublished
draft, which covers every release operation `binaries.yml` and `publish.yml` perform.
`gh release edit <tag> --draft=false` published it. `gh release view` also exposes
`isDraft` and `isImmutable`, so both states are assertable from the lane.

The probe confirmed the tag behaviour the schema describes: while the release was a
draft, `GET /repos/{owner}/{repo}/git/ref/tags/{tag}` returned 404, and the tag appeared
only on publication, pointing at the default branch head. That is the failure
`force-tag-creation` exists to prevent - without it the tag arrives after the lane needed
it, at the wrong commit. The probe release and its tag were deleted.

### Not investigated

Whether `actions/attest` subjects behave identically against a draft, and whether the
acquisition check can reach one. The first is a property of the attestation action rather
than of the release object and the subjects are local files in any case; the second is
moot while the acquisition dispatch stays behind publication.

## Sources

- `.github/workflows/release-please.yml:170-177`
- `.github/workflows/release.yml:16-21`
- `.github/workflows/binaries.yml:1480-1611`
- `.github/workflows/publish.yml:215`
- `.github/workflows/publish.yml:281-285`
- commit `37572cb6`
- https://github.com/github/docs/blob/main/content/repositories/releasing-projects-on-github/managing-releases-in-a-repository.md
- https://raw.githubusercontent.com/googleapis/release-please/v17.3.0/schemas/config.json
- https://github.com/googleapis/release-please-action/blob/5c625bfb5d1ff62eadeeb3772007f7f66fdcf071/package.json
- https://github.com/googleapis/release-please/pull/2627
- https://api.github.com/repos/nevenincs/vaultspec-core/releases/391505545
- Draft-release probe against `nevenincs/vaultspec-core`, 2026-09-18, since deleted
