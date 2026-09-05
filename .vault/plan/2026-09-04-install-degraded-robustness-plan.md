---
tags:
  - '#plan'
  - '#install-degraded-robustness'
date: '2026-09-04'
tier: L2
related:
  - '[[2026-09-04-install-degraded-robustness-adr]]'
  - '[[2026-09-04-install-degraded-robustness-research]]'
modified: '2026-09-05'
body_schema: body-v2
body_hash: 'sha256:b4ca25bfdcf9d8035387c1402aea3b509c3cf2140e9b60f6279aeab6fb08ee6f'
---

# `install-degraded-robustness` plan

Make `vaultspec-core install` protect a workspace that has nothing, and make the protection observable when it fails.

## Description

This plan executes `2026-09-04-install-degraded-robustness-adr`, which settles the provisioning layer's contract for an absent managed subject: it is created, not treated as a reason to skip. The four coupled defects the decision addresses are grounded in `2026-09-04-install-degraded-robustness-research` as R1 through R4, and the plan's Phases map onto them in the order the ADR's Implementation section layers them - derivation first, then the write path, then reconvergence, then the diagnostic.

The ordering is not cosmetic. Each defect only becomes reachable once the one before it is fixed: creating the file exposes the short block, the short block is only recoverable through a reconvergence path that does not run, and none of it is visible while the diagnostic reports the unprotected state as informational. Landing the Phases out of order would produce intermediate commits that pass their own tests and still ship a workspace that reports success without being protected.

Phase `P05` closes the loop on the filed report: the documentation workaround that stands in for this behaviour today - a platform-split file-creation instruction, its ordering caveat, and a repair walkthrough - is removed only after the behaviour it works around is real.

## Steps

### Phase `P01` - unify the sentinel derivation on the ownership surface

Makes the managed-block entry set a function of policy rather than of what happens to exist on disk when it is computed, closing the R2 ordering exposure before any Phase can trip over it.

- [x] `P01.S01` - Point the sentinel enumeration in get_recommended_entries at managed_lock_candidates so the entry set no longer depends on which locked subjects exist at call time; `src/vaultspec_core/core/gitignore.py`.
- [x] `P01.S02` - Rewrite the enumeration comment to state the ownership-surface rule and retire the companion-less-lock-path carve-out it currently justifies; `src/vaultspec_core/core/gitignore.py`.
- [x] `P01.S03` - Retire managed_lock_paths once no production caller remains, and update the cross-references in managed_lock_candidates, prune_orphaned_lock_sentinels and git_artifacts that name it; `src/vaultspec_core/core/gitignore.py`.
- [x] `P01.S04` - Add a regression test asserting the recommended entry set is identical with and without the locked subjects present on disk; `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`.

### Phase `P02` - create the ignore file when it is absent

Removes the absent-file early return so a workspace with no .gitignore is protected by the same locked atomic write that updates an existing one, which is the defect GH issue 399 reports.

- [x] `P02.S05` - Remove the absent-file early return from ensure_gitignore_block and create the file through the same advisory_lock and atomic_write_bytes path that updates an existing one; `src/vaultspec_core/core/gitignore.py`.
- [x] `P02.S06` - Keep the absent-file plus ABSENT-state call a no-op returning False, so uninstall against a workspace with no ignore file does not create one; `src/vaultspec_core/core/gitignore.py`.
- [x] `P02.S07` - Update the ensure_gitignore_block docstring to state that it creates the file, and correct the ensure_gitattributes_block docstring that currently cites the divergence; `src/vaultspec_core/core/gitattributes.py`.
- [x] `P02.S08` - Add a regression test covering creation on a fresh directory, the ABSENT no-op, and idempotence of a second call; `src/vaultspec_core/tests/cli/test_gitignore.py`.
- [x] `P02.S09` - Add an end-to-end test installing into a workspace with no ignore file and asserting the block is complete and byte-identical after a second install; `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`.
- [x] `P02.S18` - Stop the test workspace factory seeding a gitignore before every install, so the harness no longer supplies the precondition the product now provides; `src/vaultspec_core/tests/cli/workspace_factory.py`.

### Phase `P03` - reconverge the block on upgrade

Reconciles the managed block on every upgrade rather than only under --force, so a workspace that acquires a .gitignore after installation converges without a flag the reader has no reason to pass.

- [x] `P03.S10` - Reconcile the managed ignore block unconditionally in \_finalize_upgrade_manifest instead of only under the force branch; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S11` - Add a regression test asserting a workspace that gains an empty ignore file after install converges on the complete block from a plain upgrade; `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`.
- [x] `P03.S19` - Record a gitignore opt-out explicitly in the manifest so an unconditional upgrade can tell a declined block from one that was never established; `src/vaultspec_core/core/manifest.py`.

### Phase `P04` - make the unprotected state observable

Promotes an installed workspace with an absent or short managed block from an informational line to a weighed degraded signal, so the diagnosis can report the condition it exists to catch.

- [x] `P04.S12` - Emit a degraded gitignore signal for an installed workspace whose managed block is absent, rather than the informational no-file state; `src/vaultspec_core/core/diagnosis/collectors_config.py`.
- [x] `P04.S13` - Weigh the degraded gitignore states in the doctor exit code so a gate on the command reports the unprotected workspace; `src/vaultspec_core/core/diagnosis`.
- [x] `P04.S14` - Add a regression test asserting doctor reports the degraded signal and a non-zero exit code for an installed workspace with no managed block; `src/vaultspec_core/tests/cli/test_doctor.py`.
- [x] `P04.S20` - Repair an unmanaged block on install through the resolver, and leave sync to read the same absence as the opt-out gesture it already honours; `src/vaultspec_core/core/resolver_repo.py`.

### Phase `P05` - retire the documentation workaround

Removes the authored passages that stand in for this behaviour - the file-creation caveat, the unweighed-partial qualification, and the repair walkthrough - now that the behaviour they describe has changed.

- [x] `P05.S15` - Rewrite the framework manual passage that tells the reader the install does not create the ignore file and to install again after making one; `docs/framework.md`.
- [x] `P05.S16` - Update the weighed-lines table and the worked example in the verification page that document the gitignore partial state as unweighed; `docs/verification.md`.
- [x] `P05.S17` - Reconcile the remaining gitignore claims in the CLI reference and the README against the changed behaviour; `docs/CLI.md`.

### Phase `P06` - reconcile the managed blocks on any sync

The managed git blocks are repository-level, so the opt-out gesture must be recorded whichever provider a sync names; only the all-providers path did it, which becomes visible once the diagnosis weighs an unrecorded absence.

- [x] `P06.S21` - Reconcile the gitignore and gitattributes opt-outs in the single-provider sync path as well as the all-providers one; `src/vaultspec_core/core/provider_sync.py`.
- [x] `P06.S22` - Add a regression test asserting a single-provider sync records a deleted block as an opt-out; `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`.

### Phase `P07` - close the diagnosis on conditions it cannot read

An unreadable ignore file, and a collector that failed outright, both fell back to the benign absent reading - the same shape as the defect the diagnosis was just repaired for, one layer up.

- [x] `P07.S23` - Read an unreadable or undecodable ignore file in an installed workspace as unmanaged rather than absent; `src/vaultspec_core/core/diagnosis/collectors_config.py`.
- [x] `P07.S24` - Degrade the collector's own failure fallback in an installed workspace instead of reporting a clean absence; `src/vaultspec_core/core/diagnosis/diagnosis.py`.
- [x] `P07.S25` - Add regression tests covering an undecodable ignore file inside and outside an installed workspace; `src/vaultspec_core/tests/cli/test_collectors.py`.

### Phase `P08` - close the two defects the post-implementation review found

A ruling on the open architectural questions and a systematic degraded-condition sweep each returned one defect attributable to this work: an unreadable ignore file recorded as a permanent opt-out, and an uninstall that recreated a file the workspace had deleted.

- [x] `P08.S26` - Replace the boolean managed-block predicate with a three-state one so a file that cannot be read stops answering the question the caller asked; `src/vaultspec_core/core/git_artifacts.py`.
- [x] `P08.S27` - Stand the sync reconcilers down on an unreadable file instead of recording an opt-out, and log what they decided either way; `src/vaultspec_core/core/provider_sync.py`.
- [x] `P08.S28` - Gate the uninstall block reconciler on the file existing and on no recorded opt-out, so uninstall removes without provisioning; `src/vaultspec_core/core/uninstall.py`.
- [x] `P08.S29` - Add regression tests for the three-state predicate, the unreadable-file gesture, and the three uninstall paths; `src/vaultspec_core/tests/cli/test_lock_sentinel_policy.py`.

## Parallelization

Phases `P01` through `P04` carry hard ordering and must land in sequence, for the reason stated in the Description: each Phase's defect is only reachable once its predecessor is fixed, and the regression tests in each Phase assert against the behaviour the previous Phase established. Within a Phase, Step rows are sequential where a later Step tests what an earlier one writes.

Phase `P05` depends on `P01` through `P04` in full and must not begin before `P04` closes; the authored documentation may not describe the new behaviour while any part of it is unlanded. No Phase in this plan is safe to parallelize.

## Verification

- `just test unit` and `just test broad` pass with no new failures against the pre-change baseline.
- `just lint` passes, including the type lane.
- A fresh `git init` workspace with no `.gitignore` receives the complete managed block from a single `vaultspec-core install`, and a second consecutive install produces a byte-identical `.gitignore`.
- The block written by that first install is set-equal to the block written by the second - the R2 ordering exposure is closed, not merely narrowed.
- A workspace installed without a `.gitignore` that later gains an empty one converges on the complete block from `vaultspec-core install --upgrade`, with no `--force`.
- `vaultspec-core doctor` reports a degraded signal, and a non-zero exit code, for an installed workspace whose managed block is absent or short.
- `vaultspec-core uninstall` still removes the managed block and leaves the `.gitignore` file itself in place.
- Every Step row in this plan is closed, and each carries an execution record.
