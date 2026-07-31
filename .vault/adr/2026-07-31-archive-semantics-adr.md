---
tags:
  - '#adr'
  - '#archive-semantics'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:dc32a6973e97d31b7f8b42904268efe62b112704d1a76f56f021d0fab660adb3'
related:
  - "[[2026-07-31-archive-semantics-reference]]"
  - "[[2026-06-27-rename-convergence-adr]]"
---

# `archive-semantics` adr: `per-document archive contract` | (**status:** `accepted`)

## Problem Statement

Two archive surfaces coexist: the tag-scoped `vault feature archive` and the
manifest-scoped `vault archive documents`. A working hypothesis held that only
features can genuinely be archived and that the per-document path's dry run reports
success for plan archival it could not actually deliver - which matters now because
the legacy-plan retirement campaign needs to archive 46 plans whose feature tags are
shared with live, completed documents, making the tag-scoped sweep unusable.
`2026-07-31-archive-semantics-reference` verifies the hypothesis against the code and
refutes it. A decision is needed on the sanctioned archive semantics, whether
per-document plan archiving is supported, and the contract the dry run must honour.

## Considerations

- The document engine is type-agnostic, transactional, locked, and re-preflights
  under the lock; the feature engine moves files with no lock, no rollback, and no
  destination preflight (reference, two-engines finding).
- Downstream consumers already treat an archived plan as a benign steady state: the
  exec-mapping check probes the archive tree by design, and the scanner excludes
  `_archive` uniformly (reference, consumers finding).
- The dry run executes the apply's own preflight, with exactly one deterministic
  precondition it skips (the runtime-directory check) and one inherent limit
  (point-in-time validity, failed closed by the locked re-preflight on apply)
  (reference, dry-run finding).
- Feature tags do not partition cleanly in a mature corpus: legacy and modern
  documents share tags, so tag-scoped sweeps over-collect; an explicit manifest is
  the only precise instrument for sub-feature retirement.

## Considered options

- **Features-only archiving; retire the per-document verb.** Matches the disproven
  hypothesis. Rejected: it would retire the stronger engine, and leave sub-feature
  retirement (the live campaign's actual need) with no correct instrument.
- **Per-document archiving supported for all types except plans.** A plan-shaped
  carve-out has no basis in the code: the checks were explicitly built to recognize
  archived plans, so a carve-out would forbid the one case the consumers anticipate.
  Rejected.
- **Both verbs sanctioned, scoped by intent; document engine is the contract's
  reference implementation (chosen).** Feature archive for whole-feature retirement,
  document archive for explicit sub-feature curation, with the dry-run contract
  tightened by one hoisted precondition.
- **Single verb: converge feature archive to expand a tag into a manifest and
  delegate to the document engine.** Right end-state for the engine layer, too large
  to bundle into this ruling as a prerequisite; adopted as the registered follow-on
  rather than the decision's gating condition.

## Constraints

- No document is archived as part of this decision; it rules on semantics only.
- The archive layout `.vault/_archive/<vault-relative-path>` is load-bearing for the
  exec-mapping check's archive probe and for restore's path reconstruction; the
  contract fixes it as canonical.
- The dry run has no lock; making it a reservation would require holding the docs
  lock across CLI invocations, which no verb does. Point-in-time preview is the
  strongest honest guarantee available.

## Implementation

The sanctioned semantics:

- **Both archive verbs are legitimate, distinguished by scope of intent.**
  `vault feature archive` retires a whole feature - every document carrying the tag.
  `vault archive documents --manifest` retires an explicit document list and is the
  correct instrument whenever the retirement boundary is not a feature boundary,
  including plans. Per-document archiving of plans is supported, permanent, and
  already what the check layer anticipates.
- **The dry-run contract:** a green dry run means the batch passed every
  deterministic precondition of the apply at preview time, and the apply either
  performs exactly the previewed moves or fails closed as one batch - it never
  partially applies or diverges from the preview. To make the first clause fully
  true, the one apply-only deterministic check (the runtime-directory precondition)
  is hoisted into the shared preflight so the dry run evaluates it too. The
  point-in-time limitation is documented in the verb's help text rather than papered
  over.
- **Registered follow-on, not implemented here:** `archive_feature` converges onto
  the batch engine by expanding its tag match into an explicit path list and
  delegating, retiring the last unlocked, non-transactional mover in the archive
  surface. Until then the feature verb remains sanctioned but is the weaker path,
  and bulk retirements where precision matters should prefer the manifest verb.

## Rationale

The hypothesis inverted the actual quality gradient: verification shows the
per-document path is the engine built on the transactional rename machinery, while
the feature path predates it. Ruling with the code rather than the hypothesis costs
nothing and unblocks the legacy-plan retirement with the instrument that was built
for exactly that shape of work. The dry-run ruling follows from what a preview can
honestly promise without a lock: determinism is achievable and therefore required
(hence hoisting the runtime-dir check); immunity to interleaving is not achievable
and therefore excluded from the contract explicitly, with fail-closed apply as the
compensating guarantee. The convergence follow-on is registered rather than decided
into the critical path because the campaign needs semantics now, and the feature
verb's weakness is a latent robustness gap, not a correctness blocker for tag-clean
sweeps.

## Consequences

- The legacy-plan retirement campaign proceeds on `vault archive documents --manifest` with a ruled, honest contract; no plan-shaped special case exists to
  maintain.
- Archived plans leave their exec records live by design; the exec-mapping check
  reports them as benign, so a plan's archival never manufactures findings.
- One small code change follows (preflight hoist of the runtime-directory check)
  plus a help-text clarification; both are mechanical and carry no schema impact.
- The feature verb's non-transactional mover is now a recorded known weakness with a
  registered convergence path; until convergence, its dry run promises less than the
  manifest verb's, and this asymmetry is documented rather than hidden.
