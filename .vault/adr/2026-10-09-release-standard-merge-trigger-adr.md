---
tags:
  - '#adr'
  - '#release-standard'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:5951f5a8658cffc47fb9e5107c7e39e818600d112160bc4dafd57107674f0d7f'
related:
  - "[[2026-09-30-release-standard-research]]"
  - "[[2026-09-18-release-publication-ordering-release-object-lifecycle-research]]"
  - "[[2026-09-30-release-standard-adr]]"
  - '[[2026-09-18-release-publication-ordering-adr]]'
  - '[[2026-03-22-clci-release-adr]]'
---

# `release-standard` adr: `merging the core release proposal starts the autonomous release cycle` | (**status:** `accepted`)

## Problem Statement

The dispatch-only core workflow reported success after release proposal 600 merged,
although Release Please refused to refresh while that untagged release was pending. The
maintainer expected the ready proposal's Merge button to initiate the release and
explicitly authorized restoring that behavior on 2026-10-09 in this session.

## Considerations

The workflow-token tagging limitation remains established in
`2026-09-30-release-standard-research`. Draft-first publication remains established in
`2026-09-18-release-publication-ordering-release-object-lifecycle-research`. The
maintainer requires failure reporting even when downstream jobs are skipped.

## Considered options

- Keep dispatch-only releases: rejected because merging a ready proposal must suffice.
- Release on the merge push with verification before tagging: chosen; preserves proof
  and publication ordering while making Merge the release signal.
- Create tags before verification: rejected because release tags cannot be deleted.

## Constraints

This is an authorized core-only exception to `2026-09-30-release-standard-adr`. Other
repositories retain that decision. Core starts the cut from a push to main when an
untagged merged Release Please proposal exists. Ordinary pushes refresh the proposal and
never merge an open proposal automatically. Manual dispatch remains a retry and optional
prove-and-merge entry point. The routine release requires only the human Merge button;
neither workflow dispatch nor approval of bot-created check runs is a release
prerequisite.

The exact merged commit passes the full merge gate before any tag is created. Release
Please owns version, changelog, forced tag, and draft release. Binaries precede PyPI,
publication remains last, and channel pointers follow publication. Existing credentials,
fleet restrictions, and downstream dispatch boundaries remain binding. Failed candidate
selection, a blocked proposal refresh, failed proof, or failed cut must fail the
originating workflow; skipped required jobs must not become success.

## Implementation

We will select a pending merged release on both push and dispatch, route it through
proof and cut, and refresh proposals only when a push has no merged release to finish. A
final result job validates the selected path. Automatic and manual cuts share one
concurrency group. The core runbook describes Merge as the release signal. A successful
proposal gate automatically approves held merge-gate PR runs for the exact proven head
of the open GitHub Actions bot proposal. It runs in a separate job after the verdict
completes, so held runs can reuse that successful verdict. Failed proofs and moved
proposal heads never release checks.

The older release standard receives a core scope exception. The implementation wording
in `2026-03-22-clci-release-adr` and `2026-09-18-release-publication-ordering-adr` is
reconciled to this exception without removing their publication commitments.

## Rationale

The ready release proposal provides the human release approval. Requiring another
control after Merge hides a prerequisite and strands releases. Verification before
creating the permanent tag preserves the safety constraint within this interaction.

## Consequences

Core releases start automatically after merging. Verification and runner queue time
extend the merge-to-tag window; workflow changes in that window can still prevent the
workflow token from tagging. Existing maintainer recovery remains required then.
Downstream workflows retain their own failure results because publication and binary
attestations require those workflows to remain top-level runs. Acceptance records the
maintainer's instruction and does not assert deployment or publication has occurred.
