---
tags:
  - '#audit'
  - '#binary-release-bundles'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:42d63a5d90a7891d4d08729ae924336c97b3d4ea211ecf0134ae4549e1ba2dab'
related:
  - "[[2026-09-11-binary-release-bundles-plan]]"
  - "[[2026-09-11-binary-release-bundles-adr]]"
---

# `binary-release-bundles` audit: `target archive release surface`

## Scope

Reviewed the completed `S01`-`S03` Steps and ledger rows across binary finalization, archive construction, release workflow handoff, offline extraction, checksum aggregation, channel generation, validation, tests, and direct-download guidance.

## Findings

### public-archive-contract | low | One target archive is now the public binary boundary

The builder emits a product/version/target archive with stable extracted executable names, required release material, and an archive-local manifest. Raw target-qualified files remain build staging inputs. The archive tests and workflow path agree on this contract.

### metadata-finalization | low | Descriptive metadata is generated from finalized release files

Windows PE version information is applied before the executable checksum, and the archive manifest records product identity, target, runtime, platform floor, member sizes, and member hashes. The verifier rejects layout, metadata, and member-integrity drift.

### channel-convergence | low | Package channels consume the same target archives as direct downloads

Scoop now pins one Windows archive and maps its stable extracted commands. Homebrew now pins one archive per available platform branch and installs the same stable names. Target availability is derived from archive names in the release checksum set.

### release-boundary | low | The workflow does not upload raw binaries from build staging

The build job packages and verifies before uploading its unverified handoff. The offline matrix extracts the archive and runs the stable command. Release aggregation rejects unexpected non-archive files and checks archive sidecars before publication.

### completeness-window | medium | The existing release lane can attach a partial matrix before its final completeness assertion

The final target assertion and latest-release guard still prevent a partial result from being treated as complete, but the upload occurs before that assertion. If release atomicity becomes a requirement, move the completeness gate ahead of upload and channel generation in a follow-up change.

### linux-offline-handoff | high | Linux isolation still points at the archive directory

The Unix extraction steps place stable executables in `offline-bundle`, but the Linux netns mount and unshare invocation still pass `dist-bin` to the shared check. The offline gate would therefore try to execute files that are not present in that directory. Pass the extracted directory to both Linux isolation paths and add a workflow-structure regression assertion.

### stable-release-gate | high | Stable release state must wait for complete target coverage

The release lane now has an early completeness check, but its release-state transition must hold an existing release out of `latest` while validation runs and the independent release guard must be able to demote it without a constrained build runner. Keep the promote action after complete verification and ensure the guard runs on an independent runner.

### manifest-completeness | medium | Verifier must enforce every declared metadata section

The manifest declares source revision, runtime, and platform metadata, but verification currently checks only identity, archive data, and member hashes. Require those sections and reject missing or malformed values with mutation tests.

### final-recheck | low | Revision findings are resolved

The final review by the same SOL worker returned PASS. Linux isolation now receives `offline-bundle`; the release is held out of `latest`, requires complete target coverage before upload, and uses an independent hosted verification job for demotion or promotion. Manifest source revision, runtime, and platform sections are enforced with mutation coverage, and acquisition extracts target archives on Linux, macOS, and Windows. Final verification passed 73 tests, Ruff, workflow checks, and `git diff --check`.

The earlier medium completeness-window finding is superseded operationally by the pre-upload completeness gate; the post-upload release guard remains as a defensive check.

## Recommendations

Keep the archive member list, manifest schema, and expected target set as compatibility contracts. Treat changes to them as a new reviewed release-surface decision. Revisit the completeness window if the release process must never expose partial target assets, even transiently.

## Result

PASS
