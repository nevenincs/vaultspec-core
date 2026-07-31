---
tags:
  - '#adr'
  - '#typing-exemption-policy'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:ecc975d8f7ad5aac325a695df381acb64e8362c87116b2feb3d33ccc88643ce4'
related:
  - "[[2026-07-31-typing-exemption-policy-research]]"
  - "[[2026-07-30-guard-subject-integrity-adr]]"
---

# `typing-exemption-policy` adr: `categorical test-tree privacy exemption` | (**status:** `accepted`)

## Problem Statement

The strict-typing configuration carries 19 per-directory `reportPrivateUsage`
exemptions for co-located test trees, of which 2 currently suppress real findings
and 17 suppress nothing. The open question is whether a complete, machine-derived,
guard-enforced exemption set violates the project's own principle that an exemption
granted before anything needs it is how a gate stops meaning anything - and, if not,
what policy governs the set so the question is not re-litigated on every audit.
`2026-07-31-typing-exemption-policy-research` establishes the census, the tool's
expressiveness limits, and the guard's completeness contract. No prior decision
record governs this surface.

## Considerations

- The intensional rule ("co-located test trees are exempt from `reportPrivateUsage`")
  is not expressible in the tool: glob roots are silent no-ops, per-directory
  configs are undiscovered, and per-file pragmas are banned (research,
  expressibility finding).
- Membership in the set is derived from the tree by a guard, not granted by
  judgment; omission is loud and self-explaining (research, guard finding).
- The gate-erosion principle targets discretionary per-case suppression; the census
  set's scope is a closed category with a uniform recorded rationale and a single
  exempted diagnostic (research, principle finding).
- The alternative failure mode is concrete: a test tree without its entry that hits
  the gate invites publicizing internals - trading a false positive for a real
  design regression, the exact trade the exemption exists to refuse.
- Dropping the inert entries requires a need-classifier and converts routine test
  authoring into gate-then-exempt churn, re-deciding the same categorical question
  per tree (research, alternatives finding).

## Considered options

- **Drop the 17 inert entries; grant on demonstrated need.** Purist reading of the
  principle. Rejected: it fails the completeness guard as written, needs a
  per-tree need classifier to maintain, and re-litigates an already-uniform question
  on every new suite with the publicize-the-internal shortcut as the path of least
  resistance.
- **Structural single rule (glob root or shared config).** Not expressible; a glob
  encoding passes silently while checking nothing. Rejected on verified tool
  behavior, revisitable only if the tool grows glob support.
- **Keep the complete machine-derived set, ratified as one categorical decision
  (chosen).** The entries are the extensional encoding of a single rule; the guard
  is what makes the encoding a derivation instead of a discretionary list.
- **Keep the entries but weaken the guard to advisory.** Rejected: an unenforced
  completeness contract decays into exactly the hand-curated list the principle
  warns about.

## Constraints

- The exemption's scope is fixed by this record: the `reportPrivateUsage` diagnostic
  only, co-located `tests/` trees only. Production code and every other strict rule
  in test trees remain fully gated; any widening of either axis is a new decision,
  not an edit to this one.
- The encoding is hostage to today's tool behavior; the config records the glob
  no-op as a dated judgment, and the policy inherits that caveat.
- Consistent with the guard-subject policy (`2026-07-30-guard-subject-integrity-adr`),
  the completeness guard validates a source of truth - the tree and the config, both
  authored artifacts - so its subject is sound.

## Implementation

Nothing changes in the tree; this record ratifies the existing shape and fixes its
meaning:

- The 19 entries stand as the extensional encoding of one categorical decision:
  co-located test trees sit inside the privacy trust boundary of the package they
  test, so `reportPrivateUsage` is a false positive there by construction, not a
  finding to be adjudicated per occurrence.
- The completeness guard remains the owner of membership: an entry exists if and
  only if the tree exists. Entries are added and removed with the trees they cover,
  never by per-finding judgment. The load-bearing/inert distinction carries no
  policy weight - an inert entry is the category rule at rest, not an unused grant.
- The config's inline rationale comments remain the in-place documentation; this
  record is the governing decision they now trace to.

## Rationale

The knockout distinction is between granting and encoding. The principle guards
against discretionary grants because each one is a human choice that lowers the bar
for the next; a gate dies by a thousand judgment calls. Here there are no judgment
calls to accumulate: the decision was made once, categorically, on a trust-boundary
argument the config records verbatim, and the tool's own expressiveness gap forces
that single decision to be written down as N literal entries. The guard is what
keeps the encoding honest - membership is computed from the tree, so no entry can
be smuggled in for a directory the category does not cover without the category
itself being extended, which this record reserves as a new decision. Counting inert
entries as violations would mistake the encoding for the decision: the 17 are not
seventeen exemptions nobody needed, they are one exemption, correctly scoped,
written in the only syntax the tool accepts.

## Consequences

- The recurring audit finding ("17 exemptions mask nothing") is settled: inert
  entries are the expected steady state of a categorical encoding and are not
  cleanup targets.
- New co-located test suites get their entry mechanically at creation, guard-prompted,
  with no gate-then-exempt churn and no temptation to publicize internals.
- The set tracks the tree bidirectionally under the guard; a removed test tree's
  stale entry is the one drift class the guard does not currently flag, accepted as
  cosmetic since a prefix matching nothing exempts nothing.
- The policy is coupled to basedpyright's prefix-only root matching; if the tool
  gains glob roots, collapsing the entries becomes a mechanical improvement that
  preserves this record's category rule and would amend, not supersede, it.
