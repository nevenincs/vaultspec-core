---
tags:
  - '#adr'
  - '#cli-sync-vocabulary'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-sync-vocabulary-research]]'
---

# `cli-sync-vocabulary` adr: `Normalise outcome vocabulary across sync-shaped surfaces` | (**status:** `accepted`)

## Problem Statement

The CLI emits at least five different outcome vocabularies across
five sync-shaped surfaces, and seven different operation words on
the plan-revision surface. The same conceptual operation produces
different output strings depending on which command path the user
reached. The same flag (`--force`) means different things across
two top-level commands. Machine-readable outputs (`--json`) carry
top-level status fields on four of nine commands surveyed.

The framework's output is its primary user-facing contract.
Inconsistency at that contract is what makes the CLI feel
design-by-accretion to a fresh-eyes agent.

Round-1 finding S2 (hypothesis), round-2 finding S8 (plan-revision
evidence), round-3a finding S10 (sync surface evidence), and
round-3b finding S19 (`--json` consistency) form a coherent
cluster.

## Considerations

- Existing output strings are consumed by external tools. A pure
  string rewrite is a breaking change for any caller that pattern-
  matches today's words. The reversal must announce itself.
- Text and `--json` outputs come from different code paths today;
  reconciling them requires routing both through one helper.
- Some verbs name lifecycle states that are domain-specific. Plan
  steps go from open to closed; phases get renumbered. A pure
  generic vocabulary loses domain colour. Two-track output
  (generic outcome plus domain-specific annotation) is the answer.
- The audit doc itself uses backtick-quoted state names; an ADR
  that landed names directly in body prose would tempt the
  body-wiki-link check (round 3b lesson when authoring this
  audit). Backticks for state names in framework docs too.

## Constraints

- Existing pre-commit hooks call `vault check all`, `vault repair`,
  and `spec doctor`. Their outputs must remain parseable across
  the transition.
- The change must not require operators to relearn the CLI. The
  new words are intended to be more intuitive than the old, not
  cleverer.
- The `--legacy-output` escape hatch ships for one minor release
  cycle, then is removed.

## Implementation

**Outcome-state taxonomy.** Define a single enum with seven
members:

- `created` — a destination that did not exist now exists.
- `updated` — a destination that existed was changed.
- `unchanged` — destination matched source; no write.
- `removed` — destination existed; now does not.
- `restored` — destination was reset to a canonical version
  (the semantic the misnamed `revert` verb today implements).
- `skipped` — destination was excluded by precondition or
  policy.
- `failed` — write was attempted and failed.

**Source of truth.** A new helper module exposes one function
that, given a per-item result, emits both the text rendering and
the JSON payload. Every sync-shaped command paths through it.
No surface emits its own outcome string directly.

**Surfaces in scope (all sync-shaped).**

- `vaultspec-core install` (initial + dry-run).
- `vaultspec-core install --upgrade` (drop `re-seeded`; emit
  `updated` for builtins, `unchanged` for unchanged authored
  content, `restored` for builtin reverts).
- `vaultspec-core sync` (drop the conflicting "complete sync but
  non-destructive" wording from round-1 [02]; emit the same
  seven-word vocabulary).
- `vaultspec-core spec rules sync` and siblings (drop
  `added`/`skipped`; emit the canonical set).
- `vaultspec-core migrations run` (per-migration outcomes).
- `vaultspec-core vault repair` (per-fix outcomes).
- `vaultspec-core vault check ... --fix` (per-finding outcomes).

**Plan-revision surface.** The seven words `Closed`, `Retired`,
`Renumbered`, `Promoted`, `Inserted`, `Added`, `Moved` stay as
domain-specific annotations because they name plan-lifecycle
states that are meaningful. But every plan-revision command also
emits a canonical outcome word alongside, machine-readable in
`--json`:

> `Step S03 moved.` (annotation) — `updated` (canonical outcome).

The annotation is for readers; the outcome is for tools.

**`--json` outputs.** Every command that emits `--json` gains a
top-level `status` field whose value is one of the seven outcome
words (or `mixed` when a single invocation produced multiple
outcome states across items). The per-item array stays. Per-item
records each carry an `outcome` field with their individual state.

**`--force` reconciliation.** The flag means one thing across all
surfaces: "overwrite destinations whose contents would otherwise
be preserved". Today's divergence (round-1 [02]) collapses to a
single semantic. Pruning behaviour gets its own flag (`--prune`)
on commands where it is applicable; the two are no longer
conflated.

**Companion language updates.**

- The framework manual's section on CLI output gets a glossary of
  the seven outcome words.
- Builtin rule files that reference "synced", "installed", or
  "drifted" outcomes get their wording aligned to the canonical
  set.
- Agent personas update their post-command reasoning patterns to
  match: an outcome of `unchanged` is not failure; an outcome of
  `skipped` carries a reason and is interrogable; an outcome of
  `failed` is the only thing that stops the pipeline.

## Rationale

The audit's evidence is decisive: vocabulary fragmentation across
sync-shaped surfaces is one of the two large structural findings
(the other is the memory-lifecycle gap, recorded in the sibling
ADR). It is not a tactical bug; it is the visible surface of a
missing architectural decision.

A single taxonomy, sourced once and rendered both as text and as
JSON, costs less to build than the apologia for the present state.
The seven-word set covers every outcome observed in the audit
without overlap. Two-track output (canonical plus annotation)
keeps the domain-specific operation words that carry meaning
without sacrificing the consistency every other reader needs.

The `--force` reconciliation matters separately because today the
same flag does different things, and `--force` is the flag a
worried operator reaches for when something has gone wrong. A
worried operator should never be ambushed by a flag that means
something other than they remember from another surface.

## Consequences

Gains. Operator mental model collapses from five vocabularies to
one. Pre-commit hooks, CI integrations, and IDE tools can pattern-
match a single set. `--json` outputs become CI-ready at a single
field. The framework's output reads as designed rather than as
accumulated.

Difficulties. External consumers that pattern-match today's words
break on the transition. The `--legacy-output` escape hatch
softens the landing for one release.

Pitfalls. The temptation to add an eighth or ninth word for an
edge case. The taxonomy is intentionally small. New states should
land as annotations alongside an existing outcome word, not as
new outcome words, unless an honest case for a new state emerges.

Pathways. With this ADR landed, the `--json` consistency ADR
(S19) becomes mostly mechanical: the top-level `status` field is
defined, the per-item `outcome` is defined, every surface routes
through the same helper. The CI-readiness work follows from the
taxonomy decision recorded here.
