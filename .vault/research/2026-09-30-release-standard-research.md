---
tags:
  - '#research'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:aeafd15a10cd0d88fe10c06d406fc481cfb459263e3acffe3cc81d48ae95bf2f'
related: []
---

# `release-standard` research: `release tagging under the workflow token, and the vaultspec release pipelines`

Why did vaultspec-rag 0.5.3 fail to tag, do the other vaultspec repositories carry the
same exposure, and which release shapes close it? GitHub refuses the workflow token any
tag or release that targets a commit whose workflow files differ from the default
branch's head. Every vaultspec repository creates its release tags with that token, so
each one can strand a merged release whenever a workflow change lands between the
release commit's merge and its tag. Three shapes close the window: a dispatched cut that
merges and tags within seconds, a hosted runner that shortens the wait, and a GitHub App
that holds the `workflows` permission. The evidence favours the cut, which needs no new
credential; the ADR must settle the shape and how the repositories converge on it.

## Findings

### The workflow token cannot tag a commit whose workflow files differ from the head

A throwaway private repository, `nevenincs/tag-permission-probe`, held three commits: an
older one with a different workflow set, a middle one with the head's workflow set, and
the head. A workflow run on the head tried every tagging path with `GITHUB_TOKEN`
holding `contents: write`.

| Call with the workflow token                      | Differing workflow files | Same files, older commit | Head    |
| ------------------------------------------------- | ------------------------ | ------------------------ | ------- |
| `POST /git/refs` (the forced-tag path)            | 403                      | allowed                  | allowed |
| `POST /releases` creating the tag                 | 403                      | allowed                  | allowed |
| `POST /releases` as a draft                       | 403                      | not run                  | not run |
| `POST /git/refs` on a tag a maintainer pushed     | 403, not 422             | not run                  | not run |
| `POST /releases` on that tag, naming the commit   | 403                      | not run                  | not run |
| `POST /releases` on that tag, naming no commit    | allowed                  | not run                  | not run |
| Edit, upload to, or publish a release on that tag | allowed                  | not run                  | not run |

The rule is therefore "the workflow files differ", not "the commit is not the head", and
a tag that already exists does not help while the request names the commit. The workflow
token can never be granted the `workflows` permission (community discussion 121022).

release-please cannot finish such a release on a rerun. With `force-tag-creation` it
creates the tag first and ignores only a 422 (`src/github.ts:1396` at
`release-please@17.3.0`), and it always sends the release commit as `target_commitish`
(`src/github.ts:1415`). A release that already exists is relabelled and then thrown as a
duplicate (`src/manifest.ts:1272`).

### How vaultspec-rag 0.5.3 stalled

The release pull request merged at 16:52:01Z as `59c84fd7`. Its Release Please run waited
for a fleet runner and was cancelled by the job's former ten-minute timeout. At 17:12:48Z
`1ad2bc6b` merged and changed six workflow files. The next run reached release creation
at 18:17:47Z and received 403 on create-a-release (run 36603345121); a rerun of the
release commit's own run failed the same way at 19:04. A maintainer created the tag and
release at 19:15:25Z. The window was the fleet's queue wait, not a defect in the release
configuration.

### Every vaultspec release pipeline carries the exposure

Read from each repository's `main` on 2026-09-30:

| Repository          | Tag form            | Release object    | Release created by                | Downstream start      |
| ------------------- | ------------------- | ----------------- | --------------------------------- | --------------------- |
| vaultspec-core      | `vaultspec-core-v…` | draft, forced tag | Release Please on every main push | dispatch only         |
| vaultspec-rag       | `vaultspec-rag-v…`  | published, held   | a dispatched cut (`9b0df9b3`)     | dispatch only         |
| vaultspec-a2a       | `v…`                | draft, forced tag | Release Please on every main push | tag push and dispatch |
| vaultspec-dashboard | `v…`                | draft, forced tag | Release Please on every main push | call and dispatch     |
| vaultspec-marketing | `site-v…`           | published         | Release Please on every main push | dispatch              |

All five run Release Please with the workflow token on self-hosted runners. Core's
lanes are dispatch-only by guard (`dev/guards/test_automation_contracts.py:1410`). The
latest releases of vaultspec-a2a, vaultspec-dashboard and vaultspec-marketing were
created by the maintainer's account rather than the bot; why their automated path did
not produce them was not investigated.

### Options that close the window

- **A dispatched cut.** vaultspec-rag's Release Please workflow at `9b0df9b3` refreshes
  the proposal only after main's full gate passes and never releases from that path. A
  maintainer dispatches the cut: it proves the proposal's head with the full gate and
  the accelerator tiers, squash-merges with `--match-head-commit`, checks the merged
  tree equals the proven tree, and has Release Please tag seconds later. No credential
  is added. What remains open: a proposal merged by hand waits for its cut, and a
  workflow change could land in the seconds between merge and tag. The cut had not yet
  run a release on 2026-09-30.
- **A hosted runner for the release job.** Shrinks the queue wait to seconds without a
  credential, but contradicts the fleet contract every core job is checked against
  (`dev/ci_contract.py`), and the same residual window remains.
- **A GitHub App holding `contents`, `workflows` and `pull-requests` write.** Closes the
  window completely. Tags and releases it creates raise workflow events, which the
  workflow token's do not, so every tag- or release-triggered workflow must become
  dispatch-only. Its private key can write workflow files and would be readable from
  jobs on the self-hosted fleet. vaultspec-rag rejected a write-capable release App on
  2026-09-29 for a different purpose.
- **Refusing workflow changes in the merge gate while a release awaits its tag.**
  Rejected by the evidence: `1ad2bc6b` merged 31 seconds after its gate run was queued
  (run 36603275012), so the change that stalled 0.5.3 would have bypassed the gate.

### Fit with the draft-first publication order

Core publishes a release only once it is complete: Release Please creates a draft with a
forced tag and the publication lane flips it last. The cut moves when the tag is created
from "on merge" to "on dispatch" and leaves the draft untouched. The probe shows the
workflow token can still attach to and publish a draft on a tag that already exists, so
the lanes after the tag need no new permission.

Not investigated here: the trust boundary of the self-hosted fleet, which is audited
separately, and the causes of the sibling repositories' Release Please failures.

## Sources

- https://github.com/nevenincs/tag-permission-probe/actions/runs/36696418192
- https://github.com/nevenincs/tag-permission-probe/actions/runs/36697777100
- https://github.com/nevenincs/tag-permission-probe/actions/runs/36697932690
- https://github.com/orgs/community/discussions/121022
- https://github.com/nevenincs/vaultspec-rag/actions/runs/36603345121
- https://github.com/nevenincs/vaultspec-rag/actions/runs/36600835494
- https://github.com/nevenincs/vaultspec-rag/actions/runs/36603275012
- `src/github.ts:1396` at `release-please@17.3.0`
- `src/github.ts:1415` at `release-please@17.3.0`
- `src/manifest.ts:1272` at `release-please@17.3.0`
- vaultspec-rag commit `9b0df9b3`, `.github/workflows/release-please.yml`
- vaultspec-rag commits `59c84fd7`, `1ad2bc6b`
- `dev/guards/test_automation_contracts.py:1410`
- `dev/ci_contract.py`
