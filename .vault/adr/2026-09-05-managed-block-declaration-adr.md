---
tags:
  - '#adr'
  - '#managed-block-declaration'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:5186ca9d74358652464205e0695f88e8bdee677f4320785500f5c2369da1f2af'
related:
  - "[[2026-09-05-managed-block-declaration-research]]"
---

# `managed-block-declaration` adr: `A managed-block opt-out is a committed declaration, written by a verb` | (**status:** `accepted`)

## Problem Statement

Declining a vaultspec-managed git block is recorded where no teammate can see it. `2026-09-05-managed-block-declaration-research` R1 traces the three-step sequence in which one contributor's decision is erased by another's first install, and establishes that the reversal shipped for GH issue 399 is what makes the erasure reachable rather than theoretical.

A decision is needed now because the record has just been given weight. The diagnosis reads the opt-out to decide whether an absent block is degraded or benign, so a flag that cannot travel produces a workspace where one contributor's `doctor` reports a warning that another's cannot see and neither can settle. Leaving the flag where it is means shipping that.

This record settles where the opt-out lives, what writes it, and what an absent managed subject means for each of the four subjects the product manages.

## Considerations

- The per-machine store is inside the block whose deletion it records, so the record is unreadable to a fresh clone by construction - R1.
- The identical question was answered for `hooks.pre_commit`, and the module says why in its own words: the declaration is what every contributor and a fresh clone read, and a project that declines a hook "must be able to decline it once and have that survive every later sync" - R2.
- The precedence rule a second store implies already exists and is already applied - R2.
- `.gitattributes` carries clone-wide checkout normalisation, so a per-machine opt-out for it is incoherent independently of the argument for `.gitignore` - R3.
- Four contracts for an absent managed subject already coexist and three are deliberate, so a single product-wide rule would have to break one of them - R4.
- A sync that infers intent and writes a committed file is the silent host-configuration mutation `upgrade-convergence` rejects - R5.
- The interval between deleting a block and the record catching up is real, and today the diagnosis names no way to settle it - R6.
- The verb to copy exists, idempotent and exit-zero-when-satisfied - R7.
- The record that chose the manifest predates the file this one moves into - R8.

## Considered options

- **Declaration as the store, verb as the writer, deletion demoted to an announced local stand-down (chosen).** One committed source of truth, one explicit gesture, and the existing gesture keeps working without gaining the power to write a committed file. Cost: two stores and a precedence rule, plus new CLI surface.
- **Declaration as the store, sync still writes it on inference.** Removes the new verb. Rejected: it hands a guess about intent the authority to modify a committed file, which R5 shows the corpus has already rejected once.
- **Declaration as the store, verb as the only gesture.** Cleanest single path. Rejected: it breaks the deletion gesture the framework manual documents and the 2026-03-27 record promised, for readers who have been relying on it.
- **Leave the record in the manifest, document that it is per-machine.** Cheapest. Rejected on R1: documenting a limitation does not stop one contributor silently overwriting another's decision.
- **One product-wide rule for every managed subject.** Rejected on R4: `.mcp.json` absence carries no information and `.pre-commit-config.yaml` absence is a safety statement. A single rule would have to be wrong about one of them.

## Constraints

No new dependency and no frontier technology. Four existing commitments bound the work:

- The declaration is written whole, so a new key must be threaded through the reader and writer the way `hooks` is rather than merged into an existing document.
- Unknown top-level keys are ignored on read, which is what makes the schema addition additive for a workspace that meets an older reader. This was reasoned from the reader, not tested against a released build, and the plan must test it.
- The `cli-spec-gitignore` sharing policy still governs the block's contents. This record changes who may turn the block off, not what goes in it.
- The `install-degraded-robustness` contract still holds: an absent managed subject is created rather than skipped. This record adds the one thing that stops that being unconditional.

## Implementation

The declaration gains a workspace-scoped `blocks` object with a boolean per managed git block, defaulting to managed when absent so every existing workspace reads as it does today. It is workspace-scoped rather than per-package for the reason the hook policy is: a checkout has one set of git blocks however many packages are provisioned into it.

Two verb pairs write it, one per block, built from the shape `spec precommit disable|enable` already established: idempotent, reporting an already-satisfied request as success, so a provisioning script can set the policy unconditionally. They are the only writers of the key.

The per-machine manifest fields stay, demoted to what the mode fields already are - a local echo. Every reader takes the declaration first and the echo second, which is the precedence the resolver applies to the hook policy today, generalised to cover the blocks.

Deletion remains a recognised gesture and loses its authority. Sync that finds a managed block gone stands the local echo down, prints one line saying so, and names the verb that makes the decision permanent and shareable. It does not touch the declaration. The diagnosis keeps reporting the workspace as unmanaged until the declaration says otherwise, which is now a state the reader has been told how to leave.

`.gitattributes` is brought level in the same pass: the declaration key, the verb pair, the upgrade reconciliation it has never had, and the decode handling its collector and writer both lack.

## Rationale

The knockout is R1: no other option stops one contributor's install silently reversing another's decision, because no other option puts the decision somewhere the second contributor can read. Documenting the limitation leaves the defect; inference-writes-the-declaration fixes the visibility and breaks something the corpus has already decided; verb-only fixes it and breaks a documented gesture.

The choice of two stores over one is the same trade `2026-09-05-managed-block-declaration-research` R2 records the product already making for the hook policy, including the precedence rule, so this generalises an existing mechanism rather than introducing one. That matters more than the tidiness of a single store: a mechanism a maintainer already knows how to read is cheaper than a better one they do not.

Against the temptation to state one rule for every managed subject, R4 is decisive. The four contracts are not drift to be normalised; three of them encode a real difference in what an absence means. What was missing is not uniformity but a written table, so the next reader does not have to derive the difference from four call sites.

## Consequences

A decision to decline a managed block survives a clone, which it has never done. The reader gains a verb that says what it does, and the diagnosis stops reporting a warning with no stated remedy.

The cost is surface. Two new verb pairs, a schema key, and a precedence rule that must be applied consistently everywhere the flags are read - and a period in which both stores exist and can disagree. The precedence rule makes disagreement well-defined rather than impossible, which is the same bargain the mode fields already carry.

Deleting the block becomes a weaker gesture than it was. A reader who deletes it and never runs the verb gets a persistent warning rather than silence. That is deliberate and it is the point: the interval was previously closed by inferring a decision, and inferring is what this record removes.

The schema addition is additive for a workspace that meets an older reader, on the strength of a reading of the reader rather than a test. If that reading is wrong, a workspace that has declined a block silently regains it on any machine running an older release, which is the failure this record exists to prevent - the plan verifies it before the key ships.

### Displaced decisions

Two portions of `2026-03-27-cli-ambiguous-states-gitignore-adr` no longer hold, and neither displacement was recorded when it happened:

- Its constraint that the block writer must not create `.gitignore` was reversed by `2026-09-04-install-degraded-robustness-adr`, which decided the opposite without noting the conflict. That record is amended to say so.
- Its choice to track opt-out state in the manifest is displaced by this record.

The remainder of that ADR - the marker grammar, the entry policy, idempotence, line-ending preservation, orphaned-marker recovery - stands unchanged and is not superseded. Its status stays `accepted`, with the two displaced portions annotated in place, because a wholesale supersession would retire a body of decisions that are still in force.
