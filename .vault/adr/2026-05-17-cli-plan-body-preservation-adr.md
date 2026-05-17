---
tags:
  - '#adr'
  - '#cli-plan-body-preservation'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
  - "[[2026-05-17-cli-plan-body-preservation-research]]"
---

# `cli-plan-body-preservation` adr: `Plan-editing verbs must preserve author prose` | (**status:** `accepted`)

## Problem Statement

Every `vault plan step add` invocation against a plan document
that contains author-written prose silently rewrites the document
body and discards the prose. The destructive rewrite is not
documented in the verb's `--help`, not previewable with
`--dry-run`, and not announced in the post-command output. The
verb is named `add` (additive) but its observed behaviour is
`add-and-rewrite`. The plan template that ships with the
framework instructs the author to fill in the prose sections the
verb then deletes.

Three independent reproductions across two agents and two
sandboxes (Joan round 1; Xavi round 1; Xavi round 2). The
underlying bug spans the full plan-editing surface, not just
`step add`: any verb that runs through the same parse-edit-
serialise cycle is exposed.

## Considerations

- The fix can live at the parser or at the serialiser. Parser-
  side: refuse to operate on a document containing sections the
  parser does not understand, with a `vault plan canonicalise`
  pre-step. Serialiser-side: preserve unrecognised sections
  verbatim on round-trip. Serialiser-side is the better
  ergonomics; parser-side is the safer floor.
- Plan documents have known structural elements (frontmatter,
  H1, Description/Parallelization/Verification sections,
  Wave/Phase/Step rows, optional `<!-- RETIRED -->` comments).
  Any heading or block outside this set today is silently
  dropped. The fix is to recognise "unknown but preserved" as a
  third category alongside "known and round-tripped" and
  "annotation, conditionally stripped".
- The audit's round-3a positive finding noted that the
  annotations stripper already has a structural-metadata
  discriminator (`<!-- RETIRED -->` survives `--fix`). The plan-
  edit serialiser needs a comparable discriminator for author
  prose, modelled on the same pattern.
- Every plan-editing verb (`step add`, `step insert`, `step
  edit`, `step move`, `step remove`, `phase add`, `phase
  insert`, `phase edit`, `phase move`, `phase renumber`, `phase
  remove`, `wave add`, `wave insert`, `wave edit`, `wave move`,
  `wave remove`, `tier promote`, `tier demote`, `epic intent
  edit`, `step toggle`, `step check`, `step uncheck`) routes
  through the same serialiser. Fix the round-trip layer and
  every verb benefits.

## Constraints

- The serialiser must produce byte-stable output for unchanged
  documents (idempotency under the same operation twice). The
  preservation logic cannot reorder or re-whitespace untouched
  sections.
- The fix must not regress the canonicalisation work the
  serialiser is supposed to do (e.g., normalising step-row
  formatting). Known sections continue to canonicalise; unknown
  sections preserve verbatim.
- `--dry-run` must not be a separate code path that diverges
  from the real path. The verb computes the diff against the
  current file and either prints it or applies it, from one
  state-machine.

## Implementation

**Parser/serialiser shape.**

- The parser produces a structured plan model that includes a
  list of "unknown blocks" alongside the recognised structural
  elements. Each unknown block carries its verbatim source
  bytes, its position relative to known anchors (before phase
  P01, between Step S03 and the Verification heading, etc.), and
  a stable identity for round-tripping.
- The serialiser emits each unknown block in its original
  position, verbatim, with surrounding whitespace preserved.
- The annotations-stripper rule that preserves `<!-- RETIRED
  -->` markers extends to author prose blocks the same way:
  preserved by default, with explicit opt-in `--canonicalise`
  flag if the operator wants the document re-emitted in
  canonical form (which intentionally drops unknown sections).

**`--dry-run` on every plan-editing verb.**

- Every verb that mutates the document accepts `--dry-run` and
  emits a unified diff against the current file.
- The diff is the canonical preview format. JSON output is
  produced alongside text output.
- The success line on a real run reports the structural change
  (`Step S04 added`) and confirms preservation (`Body sections
  preserved: 3 (Description, Parallelization, Verification)`)
  whenever unknown blocks exist.

**Verb-name reconciliation.**

- The verb `add` continues to mean what its name says: add the
  step to the rows. The rewrite of the rest of the document is
  not a side effect of `add`; it is a separate explicit
  operation gated by `--canonicalise`.
- The destructive behaviour is opt-in, named, and announced.

**Companion language updates.**

- Plan template guidance comments are revised to drop the "write
  these sections" instruction that today conflicts with the
  CLI's behaviour. Once the serialiser preserves them, the
  instruction is honest again.
- Builtin rule files that document the plan-editing workflow
  update their worked examples to assume prose preservation.
- Agent personas update to reflect that author prose survives
  the editor. The folklore workaround ("add steps first, prose
  later") goes away.

## Rationale

Three reproductions across two agents and two sandboxes is
decisive evidence of a real, persistent bug, not an edge case.
Adding a `--dry-run` flag without fixing the underlying
round-trip layer would leave the destructive behaviour intact
but visible. The right fix is at the round-trip layer; the
`--dry-run` flag is the safety floor that becomes useful once
preservation works.

Serialiser-side preservation is preferred over parser-side
refusal because the framework's existing pattern is to fix-and-
proceed rather than refuse-and-instruct. The annotations
stripper already demonstrates this pattern works (the `<!--
RETIRED -->` discriminator). Extending the same shape to author
prose is consistent with the existing design.

Verb-name honesty matters for agent trust. `vault plan step
add` should not also rewrite the document. Separating the
canonicalisation step under its own flag means the destructive
operation has a name and a gate.

## Consequences

Gains. Author prose round-trips correctly. The plan template's
"fill in these sections" instruction stops contradicting the
CLI. Three rounds of audit folklore go away. Pre-commit hooks
that run `vault plan step check` stop fearing the side effect.

Difficulties. The parser/serialiser change is meaningful work.
Unknown-block preservation requires careful position-tracking
relative to known anchors when the surrounding structure shifts
(e.g., a new phase inserted between two existing phases). The
test surface grows: every plan-editing verb needs a regression
test for "unknown content adjacent to your edit survives".

Pitfalls. The serialiser must not become a passive copyist for
malformed input. Known sections continue to canonicalise; only
the unknown-but-positioned blocks preserve verbatim. The
discriminator must be conservative.

Pathways. Once the plan-editing surface is non-destructive,
several downstream findings become tractable: the seven
plan-revision outcome words (S8) can carry the preservation
status alongside, the `--json` output schema (S19) can include
"preserved_blocks" as a top-level field, and the framework
manual can document plan editing as a safe operation.
