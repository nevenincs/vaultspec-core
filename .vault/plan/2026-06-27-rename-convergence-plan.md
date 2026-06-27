---
tags:
  - '#plan'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
tier: L3
related:
  - '[[2026-06-27-rename-convergence-adr]]'
  - '[[2026-06-27-rename-convergence-research]]'
  - '[[2026-06-27-rename-convergence-reference]]'
---

# `rename-convergence` plan

Converge all four CLI rename CRUDs onto one transactional engine, add per-domain advisory locks, and add a feature-rename-integrity check.

## Description

This plan implements the accepted rename-convergence ADR. Wave W01 extracts a shared `RenameTransaction` engine (root-generalized containment, reverse-journal, symlink-safe restore, domain-lock acquisition) and drives `rename_feature` through it with no behavior change, gated byte-identical by the existing rename and structure suites. Wave W02 converges `resource_rename` and `hooks_rename` (the `.vaultspec` resource domain), giving them containment, case-safe rename, lock-protected rollback, and their first unit tests while preserving the `spec.*.rename` envelopes. Wave W03 converges `vault rename` (`_execute_rename`) onto the engine, retiring its duplicate link-rewriter for the shared `rewrite_incoming_refs` (incoming_rewritten becomes per-link) and gaining rollback and case-safe rename, and brings the structure-rename cascade under the docs lock. Wave W04 adds the read-only `feature-rename-integrity` check (drift classes nothing else owns), then conforms the firmware and verifies green. Grounding is in the ADR, research, and reference linked in the frontmatter.

## Steps

## Wave `W01` - Shared transactional rename engine

Extract the reverse-journal, symlink-safe restore, root-generalized containment, and domain-lock acquisition into a shared RenameTransaction engine, and drive rename_feature through it with no behavior change (the rename_feature and structure suites are the regression gate).

### Phase `W01.P01` - RenameTransaction engine module

Create the shared engine with generalized containment, journal, symlink-safe restore, and lock acquisition.

- [x] `W01.P01.S01` - Create the shared rename-engine module with root-generalized \_assert_within and the symlink-safe restore helper; `src/vaultspec_core/vaultcore/rename_engine.py`.
- [x] `W01.P01.S02` - Implement RenameTransaction: caller-supplied snapshot, containment-checked case-safe rename, record-write/create/dir, context-manager rollback, and domain-lock acquisition; `src/vaultspec_core/vaultcore/rename_engine.py`.

### Phase `W01.P02` - Converge rename_feature

Drive rename_feature through the engine with no behavior change; rename/structure suites stay byte-identical green.

- [x] `W01.P02.S03` - Drive rename_feature through RenameTransaction, passing its non-archive snapshot set, with no behavior change; `src/vaultspec_core/vaultcore/query.py`.
- [x] `W01.P02.S04` - Run the rename_feature and structure case-rename suites to confirm byte-identical behavior; `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`.

## Wave `W02` - Converge resource and hook renames

Route resource_rename (spec rules/skills/agents) and hooks_rename through the engine on the .vaultspec resource domain, gaining containment, case-safe rename, lock-protected rollback, and their first unit tests; preserve the spec.\*.rename envelopes.

### Phase `W02.P03` - Converge resource_rename

Route spec rules/skills/agents rename through the engine on the resource domain, preserving envelopes.

- [x] `W02.P03.S05` - Route resource_rename through the engine with per-base_dir containment, case-safe rename, resource-domain lock, and rollback; `src/vaultspec_core/core/resources.py`.
- [x] `W02.P03.S06` - Add real-filesystem resource_rename tests (rules/skills/agents, rollback, preserved envelopes); `src/vaultspec_core/core/tests/test_resource_rename.py`.

### Phase `W02.P04` - Converge hooks_rename

Route the hooks rename through the engine with containment, case-safe rename, and lock-protected rollback.

- [x] `W02.P04.S07` - Route hooks_rename through the engine on the resource domain; `src/vaultspec_core/core/hooks.py`.
- [x] `W02.P04.S08` - Add real-filesystem hooks_rename tests (move plus induced-failure rollback); `src/vaultspec_core/core/tests/test_hooks_rename.py`.

## Wave `W03` - Converge document rename and cascade lock

Route vault rename (\_execute_rename) through the engine, retiring its duplicate link-rewriter for the shared rewrite_incoming_refs (incoming_rewritten becomes per-link), and bring the structure-rename cascade under the docs lock; the observable wave.

### Phase `W03.P05` - Converge vault rename

Route \_execute_rename through the engine, switch to the shared link cascade, gain rollback and case-safe rename.

- [x] `W03.P05.S09` - Route \_execute_rename through the engine and switch its incoming-link rewrite to the shared rewrite_incoming_refs; `src/vaultspec_core/cli/edit_cmd.py`.
- [x] `W03.P05.S10` - Migrate the vault.rename envelope incoming_rewritten to per-link counting and update its test; `src/vaultspec_core/tests/cli/test_vault_rename.py`.

### Phase `W03.P06` - Cascade lock and concurrency safety

Bring the structure-rename cascade under the docs lock; assert serialized concurrency safety.

- [x] `W03.P06.S11` - Acquire the docs-domain lock in the structure-rename cascade fix path; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `W03.P06.S12` - Add concurrency-safety tests asserting serialized renames cause no lost update or partial state; `src/vaultspec_core/vaultcore/tests/test_rename_concurrency.py`.

## Wave `W04` - Drift check and firmware conformance

Add the read-only feature-rename-integrity check (segment-vs-tag, exec-folder-vs-tag, orphaned old-feature artifacts; defers index/grammar to existing checks), wire it into run_all_checks and the CLI, then conform the firmware and verify green.

### Phase `W04.P07` - feature-rename-integrity check

Add the read-only drift checker, wire into run_all_checks and the CLI, with real-filesystem tests.

- [x] `W04.P07.S13` - Implement check_feature_rename_integrity for segment-vs-tag, exec-folder-vs-tag, and orphaned old-feature drift; `src/vaultspec_core/vaultcore/checks/feature_rename_integrity.py`.
- [x] `W04.P07.S14` - Wire check_feature_rename_integrity into run_all_checks and the checks package exports; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `W04.P07.S15` - Add the vault check feature-rename-integrity CLI command; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `W04.P07.S16` - Add real-filesystem tests for each drift class plus a clean-vault pass; `src/vaultspec_core/vaultcore/checks/tests/test_feature_rename_integrity.py`.

### Phase `W04.P08` - Firmware conformance and verification

Document new verbs/checks in firmware, regenerate the reference, run the full gate, and close the audit.

- [x] `W04.P08.S17` - Document the converged rename verbs and the new check in the CLI mandate rule; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [x] `W04.P08.S18` - Regenerate the CLI reference, re-seed the workspace, and run the full unit gate green; `src/vaultspec_core/builtins/reference/cli.md`.

## Parallelization

Waves are strictly sequential: W02-W04 each depend on the shared engine from W01, and W03's document convergence depends on the same engine and the shared cascade. Within W02 the resource (P03) and hook (P04) convergences are independent and may proceed in parallel once the engine lands. Within W04 the check implementation (P07) is independent of everything except the engine and may be built in parallel with W02/W03, but firmware/verification (P08) runs last. Within any phase, the implementation step precedes its test step.

## Verification

- Every Step is closed (`- [x]`).
- The full unit gate passes: `pytest src/vaultspec_core -m unit`, with the rename, security, encoding, structure-case-rename, and vault-rename suites byte-identical green (the engine extraction is behavior-preserving for `rename_feature`).
- All four rename paths (`resource_rename`, `_execute_rename`, `rename_feature`, `hooks_rename`) drive the shared `RenameTransaction`: each is containment-guarded, case-safe, symlink-safe, and rolls back byte-for-byte on an induced mid-apply failure.
- `vault rename` uses the shared `rewrite_incoming_refs` (no duplicate link-rewriter remains) and never leaves a dangling link on failure.
- Concurrent renames in a domain serialize on the domain lock with no lost update or partial state.
- `vault check feature-rename-integrity` flags each drift class on a drifted vault and passes on a clean one; `vault check all` surfaces it; it does not duplicate `check_features`/`check_structure`.
- Firmware documents the converged verbs and the new check; `vaultspec-core sync` regenerates provider mirrors clean.
- vaultspec-code-review signs off in the closeout audit.
