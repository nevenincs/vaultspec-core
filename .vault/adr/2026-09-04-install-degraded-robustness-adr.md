---
tags:
  - '#adr'
  - '#install-degraded-robustness'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:1be44f597738f617c203f8c99ae971fb6b2372f0d304eb285d000a0c2258689c'
related:
  - '[[2026-09-04-install-degraded-robustness-research]]'
---

# `install-degraded-robustness` adr: `An absent managed subject is created, not a reason to skip` | (**status:** `accepted`)

## Problem Statement

`vaultspec-core install` reports success on a workspace it has not protected. The managed ignore block is written only into a `.gitignore` that already exists; on a workspace without one the install exits `0`, prints the sharing-policy statement claiming runtime by-products stay local, and leaves the advisory-lock sentinels it just created untracked by any ignore rule. `2026-09-04-install-degraded-robustness-research` reproduces this and three further defects that share its shape, and establishes that fixing the creation gate alone leaves the first block short of what a second run produces.

A decision is needed now because the four defects are coupled: each is only reachable once the one before it is fixed, and the product currently ships a documentation workaround - a platform-split `touch` instruction - in place of the behaviour. The question this record settles is what the provisioning layer's contract is when a managed subject is missing, not merely whether one particular file gets created.

## Considerations

- `ensure_gitattributes_block` already creates its subject on absence and its docstring names the divergence from the ignore path; the corpus holds two contracts for one situation - `2026-09-04-install-degraded-robustness-research` R1.
- The untracking ownership gate in `git_artifacts` derives its sentinel set from `managed_lock_candidates` while the ignore block derives its own from `managed_lock_paths`; the two disagree whenever a locked subject is absent - R2.
- A block written before the install's own writes cannot list sentinels the install is about to create; the entry set is a pre-condition snapshot consumed as a post-condition - R2.
- `install --upgrade` reconciles the block only under `--force`, so a workspace that gains a `.gitignore` after install never converges - R3.
- `doctor` classifies the unprotected workspace as `info` and its completeness comparison reuses the same snapshot the writer used, so it cannot observe the defect it exists to catch - R4.
- Ignoring a path that never materialises costs one line in a block; failing to ignore a path that does materialise costs the reader a committed per-machine artefact. The costs are asymmetric.

## Considered options

- **Create the subject when absent (chosen).** Matches the sibling `ensure_gitattributes_block`, removes the documentation workaround, and reuses the existing `atomic_write_bytes` under `advisory_lock` write path rather than adding a second one. Cost: the install writes a file the workspace did not ask for.
- **Refuse loudly.** Keep the current write behaviour and raise so the install fails rather than exiting `0`. Honest about the state, but it breaks every workspace that deliberately has no `.gitignore`, and no other managed subject in the product behaves this way. Rejected: it converts a silent gap into a hard stop without giving the reader a working install.
- **Report and continue.** Return a third state, surface it as a `warn` in `doctor` and a hint at the end of install, write nothing. Fixes only the silence. Rejected as the primary fix - the reader is still left to run a platform-specific command - but its diagnostic half is adopted independently, because a workspace whose `.gitignore` is unwritable still needs to be told.
- **Recompute the entry set after the writes instead of changing its derivation.** Would make the first block complete without touching `managed_lock_paths`. Rejected: it fixes one call site by ordering discipline that nothing enforces, and every future call site inherits the trap.
- **Replace the `ensure_*` boolean with a three-state result.** Attractive while `False` conflates "already correct" with "declined". Rejected as unnecessary under the chosen option: once absence is always resolved by creation, `False` means only "no change was needed", and the manifest flag is already derived from `has_gitignore_block` rather than from the return value.

## Constraints

No external dependency, frontier technology, or unstable parent feature is involved. The decision is bounded by three existing commitments that must not regress:

- The `cli-spec-gitignore` sharing-policy reversal: the block lists per-machine runtime by-products only, and authored content stays team-shared. Widening the sentinel derivation must not reintroduce an authored path.
- The `m_0_1_20_gitignore_reversal` migration calls the same entry point and must keep converging on a block matching current policy.
- `advisory_lock` never removes the sentinel it derives, and `prune_orphaned_lock_sentinels` only deletes empty ones. Both remain true; this record changes what is listed, not what is locked.

## Implementation

Four changes, layered from the derivation outward.

The entry derivation is unified first. `get_recommended_entries` enumerates sentinels from the full ownership surface - the same derivation the untracking gate already consumes - instead of filtering to subjects that happen to exist at call time. The ignore block and the untracker then agree by construction, and the block's content stops depending on when in the install it is computed. The existing carve-outs are untouched: the surface is still restricted to subjects inside the workspace root, and the framework-installed gate still keeps bare workspaces clean.

The write path is made symmetric next. `ensure_gitignore_block` stops returning early on an absent subject and, when the desired state is present, creates the file through the same locked atomic write that updates an existing one. The absent-plus-absent case - no file, state absent - remains a no-op. The boolean return keeps its meaning: the file changed, or it did not.

Reconvergence follows. The upgrade path reconciles the managed block on every run rather than only under `--force`, so a workspace that acquires a `.gitignore` after installation converges on its next upgrade without a flag the reader has no reason to pass. Because the block is now idempotent against a policy-derived entry set, unconditional reconciliation is a no-op on an already-correct workspace.

The diagnostic is last. An installed workspace with no managed block is a degraded state, not an informational one, and `doctor` reports it as such. The completeness comparison stops being self-confirming once it and the writer both read the policy surface rather than the disk.

## Rationale

The chosen option wins on a knockout criterion the alternatives cannot meet: it is the only one that leaves a reader with both a working install and a protected workspace after a single command on a workspace that has nothing. Refusing loudly gives protection by withholding the install; reporting and continuing gives the install by withholding protection.

Against the narrower framing in the filed issue, the deciding evidence is R2 in `2026-09-04-install-degraded-robustness-research`: creation alone produces a block that is one entry short of the block a second run writes, because the sentinel for `.gitignore` does not exist until the very call that writes the block creates it. A fix that ships only the creation gate would close the reported bug and leave its mechanism in place, which is the failure mode this codebase has learned to name - a correct check that never observes the condition it was written for.

Unifying on the full ownership surface is chosen over post-write recomputation on the asymmetry of costs noted in the considerations, and because the untracking gate already consumes that surface. Two derivations of one policy is the drift this record removes; keeping both and sequencing their callers correctly is a discipline nothing can enforce.

## Consequences

The install becomes the two commands it already claims to be. The platform-split `touch .gitignore` / `New-Item` instruction, the paragraph explaining why the order matters, and the repair walkthrough all leave the authored documentation, and the product stops having a documented workaround as the first thing a reader meets.

The managed block gets marginally wider on workspaces where a lockable subject is absent - a sentinel path is listed before, or without, its subject ever materialising. This is deliberate and cheap: an ignore entry for a path that never appears has no effect, while the reverse leaves a per-machine artefact in someone's first commit.

Two behaviours change for existing workspaces. `install --upgrade` now touches `.gitignore` where it previously did not, which will show as a diff on the first upgrade after this lands for any workspace whose block is short. And `doctor` moves an installed workspace with no managed block from `info` to a degraded signal, which raises its exit code where it previously did not - a deliberate break, and the reason the check exists.

This record reverses a constraint of `2026-03-27-cli-ambiguous-states-gitignore-adr`, which required that the block writer must not create `.gitignore` on the reasoning that a workspace without one had chosen it. That reading did not survive contact with the call site: skipping returned the same value as "already correct", so the choice the constraint protected was indistinguishable from a workspace that had simply never been asked. The constraint is annotated as displaced in that record; the rest of it stands.

The risk this opens is that creation is now unconditional for a subject the workspace may have deliberately omitted. The mitigation is scope: the file is created only when vaultspec is being installed or upgraded into that workspace, never by a read-only verb, and the uninstall path continues to remove the block rather than the file.
