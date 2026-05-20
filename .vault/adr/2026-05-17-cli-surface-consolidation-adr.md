---
tags:
  - '#adr'
  - '#cli-surface-consolidation'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-surface-consolidation-research]]'
---

# `cli-surface-consolidation` adr: `Consolidate duplicated CLI surfaces around one canonical verb each` | (**status:** `accepted`)

## Problem Statement

The CLI exposes the same conceptual operation through two
different command paths in at least three places:

- `vaultspec-core sync claude` and `vaultspec-core spec rules sync claude` are both "push spec content to claude provider"
  surfaces — and accept incompatible argument shapes (S12).
- `spec * sync` and top-level `sync` overlap significantly
  in output and effect (S13).
- `vault sanitize annotations` and `vault check annotations --fix` produce identical results (round-1 [13]).

Two-surface CRUD doubles the documentation surface, invites
silent drift, and produces real user-facing inconsistencies
(S12 is the visible drift today).

## Considerations

- Pick the canonical surface for each pair based on which
  reads naturally given the noun-verb pattern the rest of
  the framework adopts.
- A deprecation window with explicit warnings is the
  standard transition. Removing the deprecated form
  outright would break existing automation; keeping both
  forever doubles maintenance.
- The fix coordinates with the spec-crud-parity ADR (which
  defines the uniform CRUD shape including `sync`) and the
  sync-vocabulary ADR (which defines outcome words).

## Constraints

- Top-level `sync` is a common pre-commit-hook entry point.
  Removing it would break hooks. Keeping it as a documented
  fanout helper preserves the entry point while reframing
  the semantic.
- Some operators may have memorised `vault sanitize` after
  the round-1 paper-cut. The deprecation message must
  unambiguously redirect them.
- Argument-shape reconciliation between `spec * sync <provider>` and `sync <provider>` is itself part of this
  fix.

## Implementation

**`spec * sync` and `sync`.**

- The granular form `vaultspec-core spec <group> sync` is
  canonical. Each `spec` noun group exposes `sync` with
  uniform CRUD shape per the spec-crud-parity ADR.
- The top-level `vaultspec-core sync` is repurposed as a
  fanout helper that runs every `spec <group> sync` in
  sequence and emits a combined envelope. The help text
  states plainly that the top-level form is the fanout
  equivalent.
- The provider positional (`claude`, `gemini`, etc.) is
  accepted on both forms with identical semantics. S12's
  argument-shape disagreement collapses.
- The fanout's output is the seven-word outcome taxonomy
  per the sync-vocabulary ADR. Aggregated outcome is
  `mixed` when individual groups had heterogeneous
  outcomes.

**`vault sanitize annotations` and `vault check annotations --fix`.**

- `vault check annotations --fix` is canonical.
- `vault sanitize annotations` emits a deprecation warning
  on every invocation, names the canonical replacement, and
  continues to function for one release cycle.
- After the deprecation window, `vault sanitize` is removed.
  Future `vault sanitize` invocations exit non-zero with a
  message pointing at the canonical replacement.

**Reconciliation pattern for future surfaces.** Any future
verb that produces the same effect as an existing verb is
either:

- The new canonical surface, with the prior verb deprecated.
- A documented alias of an existing verb, declared as such
  in `--help`.

Silent overlap of the kind found in this finding cluster is
disallowed by the framework's own contribution discipline.

**Companion language updates.**

- The framework manual section on the CLI gets an explicit
  paragraph on canonical-vs-deprecated surfaces. The
  paragraph names every surface currently deprecated and
  every canonical replacement.
- `--help` text on every deprecated verb names the canonical
  replacement.
- Builtin rule files that reference `vault sanitize` are
  updated to reference `vault check annotations --fix`.
- Agent personas update to reach for the canonical surface
  first.
- A new `vault check deprecated-usage` check scans the
  workspace (pre-commit hook config, agent personas,
  rule files, plan templates) for invocations of deprecated
  verbs and reports them so a team can migrate before the
  removal release.

## Rationale

The audit's three findings are independent observations of
the same shape. A single architectural pass over duplicated
surfaces, with one canonical pick per pair, closes all three
findings and constrains future contributions to avoid the
same shape.

Picking `spec * sync` as canonical over top-level `sync`
follows the framework's own per-noun-group CRUD template
(spec-crud-parity ADR). Picking `vault check annotations --fix` over `vault sanitize` follows the principle that
the verb the user reaches for is `check` (with `--fix` as
the action) rather than a parallel verb tree.

The deprecation warning approach lets existing automation
keep working through the transition and gives operators a
visible path to the canonical replacement.

## Consequences

Gains. The CLI surface shrinks. Pre-commit-hook authors have
one canonical command per operation. Documentation effort
halves on the affected surfaces. The S12 argument-shape
disagreement closes.

Difficulties. Existing automation that calls
`vault sanitize` will warn through one release and break in
the next. The deprecation must be visible in release notes,
in command output, and in the framework manual.

Pitfalls. The fanout shape for top-level `sync` must
genuinely fan out (call each granular form in sequence) and
produce a faithful aggregate. A simulated fanout that
implements its own logic would re-introduce the very drift
the consolidation closes.

Pathways. With the duplicate surfaces consolidated, the
framework's command-tree becomes legible: every operation
has one canonical path, every alias is documented, every
deprecation is announced. The audit-of-the-CLI's own
"two-surface CRUD" finding cluster closes.
