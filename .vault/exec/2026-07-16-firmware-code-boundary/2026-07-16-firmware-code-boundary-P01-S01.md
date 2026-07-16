---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S01'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# Add the canonical Code-stands-alone mandate bullet (removable scaffolding, one-way reference direction, trailer carve-out) beside the Comments mandate

## Scope

- `src/vaultspec_core/builtins/system/01-core.md`

## Description

- Add the canonical Code Stands Alone mandate bullet to the Mandates list in
  `src/vaultspec_core/builtins/system/01-core.md`, directly after the Comments mandate
  it structurally mirrors.
- Propagate with install upgrade and sync so the deployed `.vaultspec/system/01-core.md`
  snapshot carries the same content.

## Outcome

The always-on core mandates now state the full canonical boundary: removable
scaffolding, the forbidden dev-metadata reference class, the one-way reference
direction, and the commit-trailer carve-out. Modified files:
`src/vaultspec_core/builtins/system/01-core.md`, `.vaultspec/system/01-core.md`.

## Notes

Provider directories are gitignored in this repo; only the builtin source and the
`.vaultspec/` snapshot are committed. Sync reports two pre-existing stale
`vaultspec-codifier` provider files unrelated to this Step.
