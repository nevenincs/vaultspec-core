---
tags:
  - '#adr'
  - '#cli-simplification-ux'
date: '2026-05-17'
modified: '2026-06-13'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-simplification-ux-research]]'
---

# `cli-simplification-ux` adr: `Decompose the CLI simplification epic into per-cluster sibling ADRs` | (**status:** `accepted`)

## Problem Statement

The rolling CLI UX audit surfaced fourteen distinct finding clusters
spanning blockers, sharp issues, vocabulary fragmentation, and a tail
of smaller paper cuts. The natural temptation is to write one large
"refactor the CLI" ADR. The audit's evidence argues against that: the
findings touch different verbs, different validators, different
templates, different agent personas, and have independent risk
profiles. A single monolithic ADR would obscure the per-cluster
trade-offs that each finding actually requires.

This ADR records the meta-decision: how the body of work decomposes
into sibling ADRs and how the umbrella plan composes them.

## Considerations

- The audit produced findings of materially different shape: deep
  architectural decisions (memory-lifecycle), code bugs (silent edit
  failure), vocabulary fragmentation (sync taxonomy), and cosmetic
  paper cuts. A single ADR cannot give each the right level of
  attention.
- Reviewers and implementers benefit from clusters small enough to
  reason about independently. Fourteen smaller ADRs are
  inspectable; one monolithic ADR is not.
- Vaultspec's framework conventions support cross-feature
  decomposition: each cluster gets its own feature tag, each ADR
  carries its own `related:` chain to research and audit, and the
  umbrella plan binds them through its own `related:` field.
- The decomposition surfaces a side benefit: the framework can be
  exercised on itself. Authoring fourteen ADRs through
  `vault add adr` is itself an audit of the scaffolder integrity
  invariant the audit found wanting.

## Constraints

- Each cluster ADR must stand alone: a reader who picks up
  `cli-spec-edit-safety` should not have to read the other thirteen
  to understand the decision.
- The umbrella plan must reference every cluster ADR so a reader
  can navigate the body of work from the plan downward.
- The umbrella feature (`cli-simplification-ux`) carries the audit
  doc and the umbrella plan. Each cluster lives under its own
  feature tag.

## Implementation

**Decomposition rule.** Each audit finding cluster maps to one
sibling ADR under its own feature tag. Cluster boundaries are
drawn so each ADR captures one architectural decision the
framework needs to make. The fourteen clusters were defined when
this ADR was authored:

- `cli-memory-lifecycle` — first-class verbs for codify,
  supersede, retire (findings B3, B9, Bridge Gap).
- `cli-spec-gitignore` — reverse default gitignore policy on the
  spec layer (finding S5, user-named critical bug).
- `cli-sync-vocabulary` — canonical seven-word outcome taxonomy
  (findings S2, S8, S10).
- `cli-scaffolder-integrity` — scaffolders never emit
  validator-illegal values (findings B2, B5).
- `cli-plan-body-preservation` — round-trip preservation of
  author prose (finding B6).
- `cli-exec-step-records` — Step-aware exec scaffolding
  (finding B1).
- `cli-spec-edit-safety` — editor resolution and honest exit
  codes (finding B7).
- `cli-rename-integrity` — atomic rename invariant (finding B8).
- `cli-spec-crud-parity` — uniform CRUD shape across spec noun
  groups (findings S9, S15, S16).
- `cli-next-step-hints` — every successful verb volunteers the
  natural next command (finding S3, round-1 hint observation).
- `cli-blast-radius-gating` — universal dry-run and force
  discipline (findings S4, S14).
- `cli-json-consistency` — uniform JSON envelope (finding S19).
- `cli-surface-consolidation` — pick canonical surfaces,
  deprecate duplicates (findings S12, S13, round-1 sanitize
  overlap).
- `cli-paper-cuts` — sweep the residual tail under a documented
  discipline.

**Plan composition.** The umbrella plan
`2026-05-17-cli-simplification-ux-plan.md` (tier L4) sequences the
fourteen clusters into five waves: Foundation, Memory architecture,
Pipeline integrity, Surface and parity, Contract and discovery.
Each wave contains the phases delivering that wave's clusters; each
phase contains the Steps delivering that cluster. The plan's
`related:` field enumerates the fourteen cluster ADRs alongside
the audit and research documents.

**Status taxonomy.** Each cluster ADR ships with
`status: accepted`. On delivery (every Step of every phase backing
the cluster closed), the cluster ADR's status moves to
`accepted (delivered)` via the supersession-aware status workflow
the memory-lifecycle ADR introduces (P04.S13 in the umbrella
plan).

**Companion language updates.**

- The framework manual gains a section on how the framework was
  used on itself for this epic. The audit-to-ADR-to-plan
  decomposition is documented as a reusable pattern.
- Agent personas update to know that a large body of work can be
  decomposed via per-cluster sub-features, with the umbrella
  feature holding the audit, research synthesis, plan, and
  delivery ADR.

## Rationale

Monolithic refactor ADRs lose the per-cluster decision detail. The
audit produced fourteen distinct clusters with different shapes;
fourteen sibling ADRs reflect that shape honestly.

The framework already supports per-feature decomposition. Using
that mechanism for the framework's own refactor is the strongest
possible signal that the decomposition pattern works at scale.

The umbrella ADR (this document) does only one thing: record the
decomposition choice. The substantive architectural calls live in
the sibling ADRs.

## Consequences

Gains. Each cluster is reviewable in isolation. The plan reads
linearly through waves. The framework dogfoods its own
multi-feature decomposition.

Difficulties. The vault now carries fifteen related ADRs (this
one plus fourteen siblings) under fourteen feature tags. The
feature-index proliferation is real but contained; each feature
has exactly one ADR, one research note, and the umbrella plan
binds them through `related:`.

Pitfalls. A reader who picks up one sibling ADR without context
might miss interdependencies (e.g., `cli-spec-gitignore` is a
precondition for `cli-memory-lifecycle`'s codify verb to do
useful work). Each sibling ADR's Rationale section names the
interdependencies it knows about; the umbrella plan's wave
ordering is the canonical source for the dependency graph.

Pathways. The decomposition pattern is reusable. Any future
large body of work surfaced by an audit follows the same shape:
audit document, per-cluster sibling ADRs under sub-feature
tags, umbrella plan, umbrella ADR that records the decomposition
choice.
