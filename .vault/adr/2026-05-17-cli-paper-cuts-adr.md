---
tags:
  - '#adr'
  - '#cli-paper-cuts'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-paper-cuts-research]]'
---

# `cli-paper-cuts` adr: `Sweep the smaller paper cuts under a shared discipline` | (**status:** `accepted`)

## Problem Statement

The audit produced a tail of smaller findings that are
individually trivial but collectively form a felt-quality
problem: unhydrated-placeholder warnings, the `--dev` flag
leaking into consumer help, `vault graph --help`'s wrong
usage line, `vault feature list`'s trailing token,
`migrations status`'s ambiguous applied entry, `spec hooks list`'s column truncation, `spec system show`'s phantom
sync target, outcome line shape variation, the "is the
workspace green" question.

Each is small. Collectively they make the CLI feel like
design-by-accretion. The fix is a one-time discipline pass
plus a small contribution check that prevents recurrence.

## Considerations

- A per-finding ADR for each paper cut would be paperwork
  noise. A single sweep ADR plus a checklist is the right
  shape.
- The discipline is preservable: every new verb gets audited
  against the same checklist before merge. The cost is small
  if applied at write time; the cost is large if applied
  retroactively.
- Several findings have already been addressed transitively
  by other ADRs (the sync-vocabulary ADR's canonical
  taxonomy fixes the outcome-line shape variation; the
  scaffolder-integrity ADR's narrowed placeholder check
  fixes the unhydrated-placeholder warnings). The sweep
  picks up the residue.

## Constraints

- Hidden flags (`--dev`) are still callable; they just do
  not render in `--help`. The framework's CLI library
  (Typer / Click) must support `hidden=True` at the
  parameter level.
- Column rendering must adapt to terminal width. Wrapping
  long event names onto a second line is acceptable;
  truncating to a width consumed by another verb is not.
- The new top-level `vaultspec-core doctor` verb is a small
  surface addition. It composes existing checks; it does
  not add new check logic.

## Implementation

**Discipline checklist.** Adopt as a documented framework
discipline. Every new CLI verb is audited against this list
at merge time:

- Output strings use canonical outcome words (sync-vocabulary
  ADR).
- `--help` describes only consumer-facing flags; developer
  flags are hidden.
- `Usage:` line accurately reflects the verb's shape (leaf
  vs. group).
- Output columns that are consumed by sister verbs do not
  truncate.
- Exit codes are honest (spec-edit-safety ADR).
- `--dry-run` is implemented if the verb writes state
  (blast-radius-gating ADR).
- `--json` envelope follows the uniform schema (json-
  consistency ADR).
- Next-step hint is registered if applicable (next-step-
  hints ADR).
- Outcome lines name what was preserved if preservation is
  part of the contract.

The checklist lives in the contribution doc.

**Specific paper-cut fixes.**

- **Unhydrated placeholders.** Implemented in the
  scaffolder-integrity ADR. The narrowed check fires only
  for tokens outside `<!-- ... -->` regions.
- **`--dev` flag rendering.** Mark `--dev` as `hidden=True`
  in the CLI framework wiring. Document developer mode in
  a contributor doc.
- **`vault graph --help` usage line.** Fix the framework
  integration so leaf commands do not render `COMMAND [ARGS]...`. The fix applies to every leaf command, not
  just `vault graph`.
- **`vault feature list` trailing token.** Remove the
  trailing token from text output. The `has_plan` semantic
  is already in the parenthesised type list.
- **`migrations status` ambiguous applied entry.**
  Disambiguate the wording. Either "Provenance: applied at
  0.1.17 (index_subfolder)" or "Applied: 0.1.17
  (index_subfolder)" depending on whether the entry is
  historical or current.
- **`spec hooks list` column truncation.** Stop truncating
  the event-name column. Render full names; allow wrapping
  if necessary.
- **`spec system show` phantom sync target.** Audit the
  verb's reference to enrolled providers; if the destination
  is missing, report it explicitly with the canonical
  outcome word `skipped` and a one-line explanation.
- **Outcome line shape.** Closed transitively by the sync-
  vocabulary ADR's single renderer.
- **Top-level `vaultspec-core doctor`.** New verb that
  composes `vault check all` and `spec doctor`. Single exit
  code. The hint mechanism from the next-step-hints ADR
  surfaces it as the recommended pre-commit gate.

**Companion language updates.**

- Contribution doc gets the discipline checklist.
- Framework manual's CLI reference notes the discipline
  pass and links to the contribution doc.
- Pre-commit hook examples are updated to call
  `vaultspec-core doctor` as the single workspace-green
  gate.
- Agent personas update to reach for `vaultspec-core doctor` as the readiness check.

## Rationale

The discipline pass is fast to execute (each item is small)
and high-leverage (the felt-quality improvement is
disproportionate to the per-item cost). Treating the items
as a sweep rather than per-finding ADRs respects the
findings' actual character.

The new top-level `doctor` verb is the small content addition
that closes the round-3a S17 "is the workspace green"
question. It composes existing surfaces rather than adding
new check logic. The operator gains a single answer.

The discipline checklist's value compounds over time. Every
new verb that ships under it inherits the consistency the
audit found missing in the older verbs.

## Consequences

Gains. The felt-quality problem closes. Future contributions
inherit the discipline. The operator's "is the workspace
green" question has a one-command answer.

Difficulties. Retroactive application of the checklist to
every existing verb is the largest piece of work in this
ADR. Some items (`vault graph --help` usage line) require
framework-library changes; others are local to a single
output string.

Pitfalls. The checklist must remain a small, enforced
contract rather than a long aspirational document. A
checklist that grows unchecked becomes noise that
contributors learn to skip. The contribution review must
gate on it.

Pathways. With the paper-cut sweep done and the discipline
codified, the audit's tail closes. Future audits surface
real new findings rather than rediscovering the same
small-roughness pattern in different corners of the CLI.
