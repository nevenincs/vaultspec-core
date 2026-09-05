---
tags:
  - '#audit'
  - '#managed-block-declaration'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:c85ede8ff11b5b1f9f572abc9dd0dc0e74d6e96f214a181d7041eda24d0fba14'
related:
  - "[[2026-09-05-managed-block-declaration-plan]]"
  - "[[2026-09-05-managed-block-declaration-adr]]"
---

# `managed-block-declaration` audit: `What moving the opt-out actually cost`

## Scope

The six phases of `2026-09-05-managed-block-declaration-plan` as landed on `fix/420-managed-block-declaration`: the declaration schema, the four verbs, the precedence applied at every reader, the `.gitattributes` parity work, and the documentation. Audited against `2026-09-05-managed-block-declaration-adr` and the clone sequence in `2026-09-05-managed-block-declaration-research` R1, which is now a test.

The decision itself is not re-argued. What follows is what executing it turned up that deciding it had not: two claims in the ADR that execution corrected, two further writers that had to be found before the decision took effect, and one error made and caught inside the work.

## Findings

### additive-only-on-the-read-side | high | An older writer drops the key, and no release can fix that retroactively

The ADR reasoned that the schema addition was additive because an older reader ignores top-level keys it does not know. That is true and it is half the question. The declaration is emitted whole from the parts the writer knows about, so any write by a build without the key discards it: a workspace that declined a block silently regains it the moment a teammate on an older release records a mode or a hook policy.

Reproduced by seeding a document with an unrecognised top-level key and calling `write_hooks_declaration`: the key was gone from the file afterwards.

The writer now reads the existing document and carries unknown top-level keys through unchanged, so the loss stops spreading forward and a key added by a later release or a companion package survives. Nothing fixes a build already in the field. The exposure is bounded to workspaces where someone still runs a release older than this one, and it closes as those upgrade - but it is the reason a decision to put a decision in a shared file has a release-ordering cost that a per-machine flag does not.

The ADR's Constraints and Consequences are amended to say this rather than the reading they carried.

### a-run-that-defeated-its-own-reconciliation | high | The sync inside an upgrade wrote the flag the upgrade then read

With both stores consulted uniformly, `install --upgrade` stopped restoring a deleted block. The upgrade runs a provider sync partway through; that sync sees the block the upgrade is about to reconcile still missing, records the per-machine stand-down, and the upgrade's own reconciliation then reads that flag and declines to act. An operator who typed an explicit provisioning command silently got nothing.

Resolved by making the precedence asymmetric and saying why: install, upgrade and the preflight repair read the declaration alone, while the verbs that infer intent from the working tree - sync, the diagnosis, uninstall - also honour the echo. An explicit provisioning command is a request; a deleted block noticed during a sync is an inference, and a request outranks an inference made about it mid-run.

This is the same shape as the defect the whole `install-degraded-robustness` feature was about - state derived from a snapshot the same run is in the middle of changing - reached from the opposite direction. It was caught by a test rather than in review.

### three-writers-not-one | high | Gating the install path left two routes that still restored a declined block

The first implementation gated the upgrade reconciler and stopped there, and the clone sequence still failed. The block came back through the fresh-install write, and after that was gated it came back again through the preflight `REPAIR_GITIGNORE` step: the diagnosis reads a *declined* block as benignly absent, and a benignly absent block is a repair candidate, so the resolver planned a repair that the executor performed.

Three writers had to be found before a committed decline actually held. There is nothing in the code that enumerates them, and nothing that would have caught a fourth. The general lesson is the one the `.gitignore` sentinel derivation already taught: a policy consulted at N call sites is a policy with N chances to be forgotten, and the fix is a single resolution point that every writer is required to pass through rather than a rule each writer remembers.

### the-fix-reintroduced-the-defect-once | medium | A fresh install initially cleared the committed declaration

Written into the first implementation, on the reasoning that "a fresh install is an opt-in by definition". It is not: cloning a project that has declared it does not want a block and provisioning it is not a request to reverse that. Left in, it would have reproduced the exact sequence this feature exists to close, by a new route, and it contradicted the ADR's own statement that the verbs are the only writers of the key.

Caught by running the research's clone sequence by hand before writing the test for it. Recorded because the reasoning was plausible enough to type and wrong enough to undo the feature, and because it was caught by exercising the scenario rather than by re-reading the diff.

### gitattributes-now-raises-the-exit-code | medium | A behaviour change for existing workspaces

`.gitattributes` gains the `UNMANAGED` signal and is weighed the way `.gitignore` is. An installed workspace that has lost the block, and has not declined it, now reports `warn` and raises `doctor`'s exit code where it previously printed `info` and did not. That is the intended repair - it is the check that was never firing - but it will surface on workspaces whose operators changed nothing.

The same run also gives that workspace a way out that it did not have: `install --upgrade` now reconciles `.gitattributes`, which it never did.

### not-investigated | low | What this audit did not cover

Concurrent writers of `workspace.json` from two processes: the write takes the advisory lock, but no contention test was run. Whether a companion package's own writer preserves unknown keys the way this one now does - the fix is in `vaultspec-core`'s writer only, and a companion with its own copy of the pattern would still truncate. Non-git workspaces. Whether `.mcp.json` should gain a declaration key after all, which the ratified contract table says it should not but which was decided from its derivation rather than from any user report.

## Recommendations

- Give the managed-block policy one enforced entry point rather than four remembered ones. Every write of a managed block should route through a helper that resolves the policy itself, so a future call site cannot restore a declined block by forgetting to ask. This closes the `three-writers-not-one` class rather than its current three instances.
- Publish the writer's unknown-key contract where a companion package author will meet it. The preservation fix is in one writer; a companion carrying its own copy of the whole-document pattern reintroduces the truncation for every key it does not know.
- Add the release-ordering note to whatever tells operators to upgrade. A committed opt-out written by this release is dropped by an older one, so a team that upgrades unevenly can lose a decision without any error appearing anywhere.
- Consider whether the per-machine echo earns its place now that the declaration exists. It resolves one case - a machine that stood down before this release - and it is the store that had to be excluded from install and upgrade to stop it defeating them. A migration that converts it to a declaration on first upgrade would let it be retired.
