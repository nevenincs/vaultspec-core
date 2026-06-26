---
generated: true
tags:
  - '#index'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-uniform-rename-P01-S01]]'
  - '[[2026-06-26-uniform-rename-P01-S02]]'
  - '[[2026-06-26-uniform-rename-P01-S03]]'
  - '[[2026-06-26-uniform-rename-P01-S04]]'
  - '[[2026-06-26-uniform-rename-P02-S05]]'
  - '[[2026-06-26-uniform-rename-P02-S06]]'
  - '[[2026-06-26-uniform-rename-P02-S07]]'
  - '[[2026-06-26-uniform-rename-P02-S08]]'
  - '[[2026-06-26-uniform-rename-P02-S09]]'
  - '[[2026-06-26-uniform-rename-P03-S10]]'
  - '[[2026-06-26-uniform-rename-P03-S11]]'
  - '[[2026-06-26-uniform-rename-P03-S12]]'
  - '[[2026-06-26-uniform-rename-P04-S13]]'
  - '[[2026-06-26-uniform-rename-P04-S14]]'
  - '[[2026-06-26-uniform-rename-P04-S15]]'
  - '[[2026-06-26-uniform-rename-P04-S16]]'
  - '[[2026-06-26-uniform-rename-P04-S17]]'
  - '[[2026-06-26-uniform-rename-P04-S18]]'
  - '[[2026-06-26-uniform-rename-P04-S19]]'
  - '[[2026-06-26-uniform-rename-P04-S20]]'
  - '[[2026-06-26-uniform-rename-P04-S21]]'
  - '[[2026-06-26-uniform-rename-P05-S22]]'
  - '[[2026-06-26-uniform-rename-P05-S23]]'
  - '[[2026-06-26-uniform-rename-P05-S24]]'
  - '[[2026-06-26-uniform-rename-adr]]'
  - '[[2026-06-26-uniform-rename-plan]]'
  - '[[2026-06-26-uniform-rename-reference]]'
  - '[[2026-06-26-uniform-rename-research]]'
---

# `uniform-rename` feature index

Auto-generated index of all documents tagged with `#uniform-rename`.

## Documents

### adr

- `2026-06-26-uniform-rename-adr` - `uniform-rename` adr: `uniform feature rename verb with atomic multi-surface rewrite` | (**status:** `accepted`)

### exec

- `2026-06-26-uniform-rename-P01-S01` - Create the shared rename-primitives module and move the case-safe path renamer into it
- `2026-06-26-uniform-rename-P01-S02` - Move the related-link rewrite engine and its regexes into the shared module
- `2026-06-26-uniform-rename-P01-S03` - Re-point the structure check to import the rename primitives from the shared module
- `2026-06-26-uniform-rename-P01-S04` - Run the structure case-rename suite to confirm no behavior change
- `2026-06-26-uniform-rename-P02-S05` - Add feature-tag validation helpers for kebab-case, schema tag form, and reserved DocType names
- `2026-06-26-uniform-rename-P02-S06` - Implement the anchored date-keyed feature-segment path transform for docs, exec folder, and exec records
- `2026-06-26-uniform-rename-P02-S07` - Implement the old-to-new tag-block rewriter with flow-to-block normalization
- `2026-06-26-uniform-rename-P02-S08` - Implement rename_feature plan computation and collision detection with refuse-default and force-merge
- `2026-06-26-uniform-rename-P02-S09` - Implement reverse-journal apply with rollback, index regeneration, stamp refresh, and graph-cache invalidation
- `2026-06-26-uniform-rename-P03-S10` - Add the cmd_feature_rename command with two positionals and dry-run, force, json, no-hints, and target options
- `2026-06-26-uniform-rename-P03-S11` - Render human output with renamed count, old-to-new paths, cross-link rewrite count, collision warnings, and a next-step hint
- `2026-06-26-uniform-rename-P03-S12` - Emit the versioned json envelope vaultspec.vault.feature.rename.v1 with canonical status
- `2026-06-26-uniform-rename-P04-S13` - Test validation guards for empty, invalid, reserved target, missing source, and collision refusal
- `2026-06-26-uniform-rename-P04-S14` - Test dry-run returns the full plan and mutates nothing on disk
- `2026-06-26-uniform-rename-P04-S15` - Test happy-path rewrite of filenames, the feature tag, and related links
- `2026-06-26-uniform-rename-P04-S16` - Test exec folder and exec record rename with preserved plan-date prefix
- `2026-06-26-uniform-rename-P04-S17` - Test cross-feature incoming wiki-link rewrite in other features documents
- `2026-06-26-uniform-rename-P04-S18` - Test reverse-journal rollback restores original state after an induced mid-apply failure
- `2026-06-26-uniform-rename-P04-S19` - Test force-merge into an existing feature and refusal on per-file path collision
- `2026-06-26-uniform-rename-P04-S20` - Test flow-style tags normalization and feature index delete-and-regenerate
- `2026-06-26-uniform-rename-P04-S21` - Test the rename command end-to-end including the json envelope
- `2026-06-26-uniform-rename-P05-S22` - Document the vault feature rename verb in the CLI mandate rule
- `2026-06-26-uniform-rename-P05-S23` - Add the rename verb to the local CLI reference
- `2026-06-26-uniform-rename-P05-S24` - Propagate firmware edits with vaultspec-core sync and confirm mirrors regenerate clean

### plan

- `2026-06-26-uniform-rename-plan` - `uniform-rename` plan

### reference

- `2026-06-26-uniform-rename-reference` - `uniform-rename` reference: `existing rename machinery and feature binding surfaces`

### research

- `2026-06-26-uniform-rename-research` - `uniform-rename` research: `uniform feature-tag rename across all binding surfaces`
