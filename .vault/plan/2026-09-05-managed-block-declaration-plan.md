---
tags:
  - '#plan'
  - '#managed-block-declaration'
date: '2026-09-05'
tier: L2
related:
  - '[[2026-09-05-managed-block-declaration-adr]]'
  - '[[2026-09-05-managed-block-declaration-research]]'
modified: '2026-09-05'
body_schema: body-v2
body_hash: 'sha256:0eccf8d9184f3159c7be35913bfba401ea2d536695916273f37da47ed18b07a1'
---

# `managed-block-declaration` plan

Move the opt-out for the managed git blocks out of per-machine state and into the committed declaration, and give it a verb that writes it.

## Description

This plan executes `2026-09-05-managed-block-declaration-adr`, grounded in `2026-09-05-managed-block-declaration-research`. It closes GH issue 420, and GH issue 410 falls to the same work because bringing `.gitattributes` level with `.gitignore` is part of the decision rather than a separate errand.

The phases follow the layering the ADR sets out: the schema first, because every other phase reads it; then the verbs that write it; then the readers, which must apply the declaration-over-manifest precedence consistently or the two stores will disagree in ways that depend on which call site a reader hits; then the `.gitattributes` parity work; then the documentation.

One constraint drives the ordering more than the others. `_write_document` writes the declaration whole and takes each half as a required parameter precisely so a caller cannot silently drop the half it did not name. Adding a third half means every existing caller must be updated in the same change, or a write that forgets it erases a committed opt-out - which is the failure this plan exists to prevent, arriving by a new route.

## Steps

### Phase `P01` - add the blocks declaration to the committed schema

Every other phase reads or writes this key, and the whole-document writer takes each half as a required parameter so a caller cannot drop the one it did not name - adding a third half is a single change across every writer.

- [x] `P01.S01` - Add a BlocksDeclaration carrying one boolean per managed git block, defaulting to managed so an undeclared workspace reads exactly as it does today; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `P01.S02` - Add the lenient-on-absence, strict-on-malformed reader for the blocks object, matching the contract read_hooks_declaration honours; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `P01.S03` - Take the blocks half as a third required parameter of the whole-document writer and update both of its callers in the same change; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `P01.S04` - Add the locked upsert that persists the blocks declaration while leaving packages and hooks untouched; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `P01.S05` - Add tests covering the default, an explicit decline, a malformed blocks object, and a round-trip that leaves packages and hooks byte-identical; `src/vaultspec_core/tests/cli/test_managed_block_declaration.py`.

### Phase `P02` - give the declaration a verb that writes it

A committed decision needs an explicit gesture; sync inferring one and then writing a committed file is the silent mutation the corpus already rejected.

- [x] `P02.S06` - Add the spec gitignore disable and enable verbs, idempotent and reporting an already-satisfied request as success; `src/vaultspec_core/cli/spec_cmd_hooks.py`.
- [x] `P02.S07` - Add the spec gitattributes disable and enable twins over the same implementation; `src/vaultspec_core/cli/spec_cmd_hooks.py`.
- [x] `P02.S08` - Register both verb groups on the spec app and regenerate the CLI reference; `docs/CLI.md`.
- [x] `P02.S09` - Add tests asserting each verb writes only its own key, is idempotent, and exits zero when the requested state already holds; `src/vaultspec_core/tests/cli/test_managed_block_declaration.py`.

### Phase `P03` - apply declaration-over-manifest precedence at every reader

Two stores are only well-defined if every reader resolves them the same way; a reader that consults the echo alone reinstates the defect for the paths it governs.

- [x] `P03.S10` - Add one resolution helper that answers whether a block is managed, declaration first and manifest echo second; `src/vaultspec_core/core/gitignore.py`.
- [x] `P03.S11` - Read the resolution helper in the upgrade reconciler instead of the manifest field alone; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S12` - Stand the per-machine echo down in the sync reconciler without writing the declaration, and print the line that names the verb; `src/vaultspec_core/core/provider_sync.py`.
- [x] `P03.S13` - Read the resolution helper in the diagnosis collector so an undeclared workspace stays weighed and a declined one does not; `src/vaultspec_core/core/diagnosis/collectors_config.py`.
- [x] `P03.S14` - Read the resolution helper in the uninstall reconciler, replacing the manifest field it consults today; `src/vaultspec_core/core/uninstall.py`.
- [x] `P03.S15` - Clear the per-machine echo on install and on --upgrade --force, and leave the committed declaration to the verbs alone; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S16` - Name the settling verb in the doctor row for an unmanaged block, which carries no hint today; `src/vaultspec_core/cli/spec_cmd_doctor.py`.
- [x] `P03.S17` - Add an end-to-end test for the clone sequence in research R1, which fails before this phase; `src/vaultspec_core/tests/cli/test_managed_block_declaration.py`.
- [x] `P03.S25` - Read the declaration alone in install, upgrade and the preflight repair, so a sync partway through a run cannot defeat the reconciliation that run exists to perform; `src/vaultspec_core/core/git_artifacts.py`.
- [x] `P03.S26` - Gate the preflight gitignore and gitattributes repairs on the declaration, the route by which a declined block was still being restored; `src/vaultspec_core/core/executor.py`.

### Phase `P04` - bring gitattributes level with gitignore

The twin carries clone-wide checkout policy and is a phase behind on the declaration key, the upgrade reconciliation, and the decode handling.

- [x] `P04.S18` - Reconcile the gitattributes block on every upgrade, on the same terms the gitignore block is reconciled; `src/vaultspec_core/core/provision.py`.
- [x] `P04.S19` - Catch the decode failure in the gitattributes writer so an undecodable file raises a typed error rather than a traceback; `src/vaultspec_core/core/gitattributes.py`.
- [x] `P04.S20` - Catch the decode failure in the gitattributes collector so an unreadable file stops reading as absent; `src/vaultspec_core/core/diagnosis/collectors_config.py`.
- [x] `P04.S21` - Add tests for the upgrade reconciliation, the typed error, and the collector reading; `src/vaultspec_core/tests/cli/test_managed_block_declaration.py`.

### Phase `P05` - state the contract the reader now has

The per-subject table the ADR ratifies exists in no authored document, and the deletion gesture now means something different from what the manual says it means.

- [x] `P05.S22` - Replace the framework manual passage describing deletion as the opt-out gesture with what deletion and the verb each now do; `docs/framework.md`.
- [x] `P05.S23` - Add the per-subject contract table for an absent managed subject, which no authored document states today; `docs/framework.md`.
- [x] `P05.S24` - Carry unknown top-level keys through the whole-document write, after testing showed an older writer drops them, and record what that does and does not fix; `src/vaultspec_core/core/workspace_mode.py`.

## Parallelization

`P01` blocks everything: the schema is what the other phases read and write. `P02` and `P03` both depend on it and on nothing else, so they could be taken in either order, but `P03` is easier to verify once the verbs in `P02` exist to set up its fixtures. `P04` depends on `P01` for the declaration key and on `P03` for the precedence helper it reuses. `P05` depends on all four and must not begin before `P04` closes.

Within `P01`, the step that adds the parameter to `_write_document` and the step that updates its callers are one change split for reviewability and must land together.

## Verification

- `just test unit`, `just test broad`, and `just test repo` pass with no new failures against the pre-change baseline.
- `just lint` passes end to end.
- A workspace that runs `spec gitignore disable` has `blocks.gitignore` false in a committed `workspace.json`, and a fresh clone plus `install` leaves the block absent - the sequence in research R1, which fails today.
- `install --force` clears the declaration, and is the only install path that does.
- Deleting the block and running `sync` stands the per-machine echo down, prints one line naming the verb, and does not modify `workspace.json`.
- `doctor` keeps reporting `unmanaged` for a workspace whose declaration still says managed, and the row names the verb that settles it.
- A `workspace.json` written by this version and read by a build without the key round-trips the key rather than dropping it, or the plan records that it does not and the ADR's additive claim is corrected.
- `install --upgrade` reconciles `.gitattributes` on the same terms as `.gitignore`, and an undecodable `.gitattributes` produces a typed error rather than a traceback.
- Every step in this plan is closed and carries a ledger row.
