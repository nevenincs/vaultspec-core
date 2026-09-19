---
tags:
  - '#plan'
  - '#docs-curation'
date: '2026-02-21'
tier: L1
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:00a0f594ea20812af0742db696dcfa1e160c9b1d03fb7c9887e7522aeef8f877'
---

# `docs-curation` plan

Auto-fix frontmatter, tag, and comment-block violations on three untracked `team-mcp-integration` vault records.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-02-21-docs-curation-exec`), which is a vault audit rather than a
sequenced execution log: it records a scoped review of three vault documents
with per-file violation tables and confirms every violation was auto-fixed
in place. The Steps below restate the three files it reports as fixed; they
are closed on that evidence, not re-executed.

Decision coverage: no costly decision is involved and no ADR governs this
curation pass. A later, unrelated `docs-curation` ADR
(`2026-03-23-docs-curation-adr`) exists but is a separate proposed scaffold
postdating this audit; it does not govern this record's mechanical fixes and
is not linked here.

## Steps

- [x] `S01` - fix the missing comment block and quoted date on the team-mcp-integration ADR; `.vault/adr/2026-02-20-team-mcp-integration-p1-adr.md`.
- [x] `S02` - migrate unsupported frontmatter keys to body prose and fix tags on the team-mcp surface design reference; `.vault/reference/2026-02-20-team-mcp-surface-design-reference.md`.
- [x] `S03` - migrate unsupported frontmatter keys to body prose and fix tags on the team-mcp-integration research; `.vault/research/2026-02-20-team-mcp-integration-research.md`.

## Parallelization

None. The three fixes touch independent files and were applied in one
audit pass; the work is complete, so no container is available for
concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs: it
confirms post-fix frontmatter shape, tag counts, and `related:` wiki-link
targets for all three files.
