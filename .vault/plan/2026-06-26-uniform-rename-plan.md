---
tags:
  - '#plan'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
tier: L2
related:
  - '[[2026-06-26-uniform-rename-adr]]'
  - '[[2026-06-26-uniform-rename-research]]'
  - '[[2026-06-26-uniform-rename-reference]]'
---

# `uniform-rename` plan

A uniform `vault feature rename` verb that atomically rewrites every binding surface of a feature tag, then conforms the firmware to it.

## Description

This plan implements the accepted ADR for a uniform feature rename. Phase P01 extracts the case-safe path renamer and the `related:` link-rewrite engine from the structure check into a shared module so one implementation serves both the check and the new backend. Phase P02 builds `rename_feature` in `query.py` with validation, plan computation, and a reverse-journal apply that restores the original state on any failure, covering filenames, the exec folder and records, the `#feature` tag, `related:` links, and the regenerated index while never touching body prose. Phase P03 exposes the backend as `vault feature rename` with output and a versioned JSON envelope mirroring `archive`. Phase P04 covers every guard, the happy path, rollback, and merge with real-filesystem factory-based tests. Phase P05 conforms the firmware to document the verb and propagates it through `sync`. Grounding lives in the ADR, research, and reference linked in the frontmatter.

## Steps

### Phase `P01` - Shared-module extraction

Extract the case-safe path rename and related-link rewrite primitives into a shared module so the structure check and the rename backend call one implementation.

- [x] `P01.S01` - Create the shared rename-primitives module and move the case-safe path renamer into it; `src/vaultspec_core/vaultcore/rename_ops.py`.
- [x] `P01.S02` - Move the related-link rewrite engine and its regexes into the shared module; `src/vaultspec_core/vaultcore/rename_ops.py`.
- [x] `P01.S03` - Re-point the structure check to import the rename primitives from the shared module; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P01.S04` - Run the structure case-rename suite to confirm no behavior change; `src/vaultspec_core/vaultcore/checks/tests/test_structure_case_rename.py`.

### Phase `P02` - Backend rename_feature

Implement the rename_feature backend with validation, plan computation, and reverse-journal apply that restores original state on any failure.

- [x] `P02.S05` - Add feature-tag validation helpers for kebab-case, schema tag form, and reserved DocType names; `src/vaultspec_core/vaultcore/query.py`.
- [x] `P02.S06` - Implement the anchored date-keyed feature-segment path transform for docs, exec folder, and exec records; `src/vaultspec_core/vaultcore/query.py`.
- [x] `P02.S07` - Implement the old-to-new tag-block rewriter with flow-to-block normalization; `src/vaultspec_core/vaultcore/query.py`.
- [x] `P02.S08` - Implement rename_feature plan computation and collision detection with refuse-default and force-merge; `src/vaultspec_core/vaultcore/query.py`.
- [x] `P02.S09` - Implement reverse-journal apply with rollback, index regeneration, stamp refresh, and graph-cache invalidation; `src/vaultspec_core/vaultcore/query.py`.

### Phase `P03` - CLI command

Expose the backend as the vault feature rename CLI command with human and JSON output mirroring the archive verb.

- [x] `P03.S10` - Add the cmd_feature_rename command with two positionals and dry-run, force, json, no-hints, and target options; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S11` - Render human output with renamed count, old-to-new paths, cross-link rewrite count, collision warnings, and a next-step hint; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P03.S12` - Emit the versioned json envelope vaultspec.vault.feature.rename.v1 with canonical status; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P04` - Tests

Cover the backend and command with real-filesystem, factory-based tests for every guard, the happy path, rollback, and merge.

- [x] `P04.S13` - Test validation guards for empty, invalid, reserved target, missing source, and collision refusal; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S14` - Test dry-run returns the full plan and mutates nothing on disk; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S15` - Test happy-path rewrite of filenames, the feature tag, and related links; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S16` - Test exec folder and exec record rename with preserved plan-date prefix; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S17` - Test cross-feature incoming wiki-link rewrite in other features documents; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S18` - Test reverse-journal rollback restores original state after an induced mid-apply failure; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S19` - Test force-merge into an existing feature and refusal on per-file path collision; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S20` - Test flow-style tags normalization and feature index delete-and-regenerate; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.
- [x] `P04.S21` - Test the rename command end-to-end including the json envelope; `src/vaultspec_core/tests/cli/test_feature_rename_cli.py`.

### Phase `P05` - Firmware conformance

Conform the firmware to document the new rename verb and propagate it through sync.

- [x] `P05.S22` - Document the vault feature rename verb in the CLI mandate rule; `.vaultspec/rules/rules/vaultspec-cli.builtin.md`.
- [x] `P05.S23` - Add the rename verb to the local CLI reference; `.vaultspec/rules/reference/cli.md`.
- [x] `P05.S24` - Propagate firmware edits with vaultspec-core sync and confirm mirrors regenerate clean; `.claude/rules/vaultspec-cli.builtin.md`.

## Parallelization

Phases are largely sequential. P02 depends on the shared module from P01; P03 depends on the backend from P02; P04 depends on P02 and P03; P05 depends on a green, tested verb from P04. Within P02, the validation helpers (S05), the path transform (S06), and the tag rewriter (S07) are independent and may be built in parallel, but plan computation (S08) and the reverse-journal apply (S09) depend on all three. Within P04, the test Steps are mutually independent and may be authored in parallel once the backend and command exist. P05 runs last, entirely after P04 is green.

## Verification

- Every Step in the plan is closed (`- [x]`).
- The structure case-rename suite and the full unit gate pass: `pytest src/vaultspec_core -m unit`.
- `vault feature rename` renames a feature across filenames, the exec folder and records, the `#feature` tag, `related:` links, and the feature index, with no free-form body prose changed.
- A dry-run reports the full plan and mutates nothing; an induced mid-apply failure leaves the vault byte-identical to its pre-rename state.
- `--force` merges into an existing feature and refuses per-file path collisions; reserved and invalid targets are rejected.
- After a rename, `vault check all` passes with no dangling links and a consistent feature index.
- The firmware documents the verb and `vaultspec-core sync` regenerates provider mirrors clean.
- vaultspec-code-review signs off in the closeout audit.
