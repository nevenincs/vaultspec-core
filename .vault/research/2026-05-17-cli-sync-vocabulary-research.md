---
tags:
  - '#research'
  - '#cli-sync-vocabulary'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-sync-vocabulary` research: `Sync-shaped surfaces emit five different vocabularies`

Synthesis note for the vocabulary-fragmentation cluster. Captures
the evidence behind the sibling ADR that proposes a single
outcome-state taxonomy for every CLI surface that reconciles
state.

## Findings

### Five sync vocabularies for one conceptual operation

Joan's round-3a survey collected the following outcome words from
five sync-shaped CLI surfaces:

- `added` and `skipped` from `vaultspec-core spec rules sync` (and
  the sibling `spec skills sync`, `spec agents sync`).
- `updated` from `vaultspec-core sync` (the top-level).
- `re-seeded` from `vaultspec-core install --upgrade`.
- `new` from `vaultspec-core install --dry-run`.
- An implicit fifth: `unchanged` does not appear consistently — some
  surfaces emit it, some surfaces stay silent on no-op.

Same conceptual operation (reconcile state A against state B in
five places), five different output vocabularies. Round-1 finding
S2 was the original hypothesis; Joan v3 produced decisive evidence
in round-3a S10.

### Seven outcome words on the plan-revision surface

Round-2 finding S8 (Joan): the plan-revision verbs produce
`Closed`, `Retired`, `Renumbered`, `Promoted`, `Inserted`, `Added`,
`Moved` as outcome strings. The grammar is inconsistent. Some are
past-perfect verbs operating on the entity, some refer to the
operation performed. A reader cannot parse outcome consistently
without translating each verb individually.

### `--json` outputs do not summarise consistently either

Round-3b S19 (Xavi): of nine `--json` outputs surveyed, four
carried a top-level `status` field (the gold-standard pattern is
`spec mcps status --json`). The most consequential for CI — `vault
check all --json` — does not. CI integrators have to iterate the
per-check array to learn whether the gate passed.

### Verb collisions across surfaces

`install --force` and `sync --force` accept the same flag with
different overwrite semantics (round 1 finding [02]). `vault check
annotations --fix` and `vault sanitize annotations` produce
identical outputs from different command paths (round 1 finding
[13]). `spec rules sync claude` and `vaultspec-core sync claude`
accept incompatible argument shapes (round 3a S12). The same words
do not mean the same thing across surfaces.

### Why the divergence exists

The five sync-shaped surfaces grew independently. Each was added
when its functional need arose; the output vocabulary was decided
locally by each. There is no central taxonomy that every surface
checks against, and there is no rendering helper that emits a
shared vocabulary into both text and JSON outputs from a single
source of truth.

The divergence is a design-by-accretion problem, not a feature.

## Vocabulary candidate set

A normalised taxonomy that covers every observed outcome:

- `created` — new state was written that did not exist before.
- `updated` — existing state was changed.
- `unchanged` — state was already correct; no write happened.
- `removed` — state was deleted.
- `restored` — state was rolled back to a canonical version
  (the verb that the broken-named `revert` should aspire to).
- `skipped` — state was not touched because a precondition
  failed (e.g., explicit exclusion).
- `failed` — write attempted, error encountered.

Seven words covering every observed sync-shaped outcome across the
CLI, with no internal overlap and no ambiguity.

## Constraints identified

- Existing text outputs are part of the user-facing contract. Some
  consumers (scripts, IDE integrations) may parse the current
  words. The change ships behind a version bump or with an
  explicit `--legacy-output` flag for one release.
- `--json` outputs are similarly contracted. The migration must
  add the top-level `status` field without removing existing
  fields, and document the schema.
- The plan-revision verbs (`Closed`, `Retired`, `Renumbered`,
  `Promoted`, etc.) refer to plan-specific lifecycle states that
  do not all collapse into the seven-word taxonomy. Those verbs
  may keep their plan-specific names AND emit a generic outcome
  word (`updated`, `restored`) alongside.

## Recommendation

Define a single outcome-state vocabulary used by every CLI surface.
Source it from one helper used by every renderer. Apply to both
text and `--json` outputs. Carry plan-specific operation names as
secondary annotations. Full design in the sibling ADR.
