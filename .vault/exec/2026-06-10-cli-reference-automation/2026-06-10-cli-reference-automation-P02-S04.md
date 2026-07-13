---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S04
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# Produce a decision ADR weighing a Typer-surface auto-generator for the bundled reference against the existing hand-authored-plus-drift-guard approach, deciding whether to build it (D6 deferral)

## Scope

- `.vault/adr`

## Description

- Read the originating plan row, the firmware-wording-review ADR (D6 deferral) and audit (REVIEW-005 lineage), the bundled reference artifact, the existing drift guard, and the Typer app wiring to ground the decision.
- Investigated Typer introspection feasibility: confirmed the app object exposes the command tree via `registered_commands`/`registered_groups` and per-option metadata via the Click parameter objects, the same surface both existing drift guards already walk.
- Mapped the reference structure into a derivable-versus-prose split and identified the curated zones introspection cannot infer.
- Scaffolded the decision ADR via `vaultspec-core vault add adr`, authored its body at status accepted, formatted it, and stripped template annotations.
- Closed plan row S04.

## Outcome

The decision is build. The ADR records an accepted decision to build a Typer-introspection reference generator, resolving the firmware-wording-review D6 deferral.

Design summary captured in the ADR for the downstream implementation Step: the generator lives as a `spec`-group verb (`vaultspec-core spec reference generate`), reusing the Typer tree walk the drift guard already proves. It emits the mechanically derivable zones (command-inventory signatures, per-command option tables, argument enumerations, declared exit codes) and preserves the hand-written prose zones (entry-point table, global-options narrative, sync-vocabulary section, grouped CRUD table, consolidated `vault check`/`vault plan` paragraphs, environment-variable table) through a managed/unmanaged-region scheme so no curated prose is lost. A `--check` mode renders into memory, diffs against the committed `cli.md`, and exits non-zero on mismatch; CI and pre-commit run it as a generated-content-up-to-date gate. The existing drift guard is retained unchanged as an independent coverage backstop. A codification candidate (`generated-reference-is-cli-owned`) is named: generated regions are updated only via the generator, never hand-edited.

## Notes

Row order put S04 first by design: the feature lifecycle gate blocks any exec record for `cli-reference-automation` until an ADR tagged `#cli-reference-automation` exists. The ADR was therefore created before this Step Record could be scaffolded, so the decision artifact necessarily precedes its own execution log. The scaffold emitted a no-research-document warning for the feature; this is expected for a follow-up plan's design-gate ADR whose provenance is the originating plan and the prior firmware-wording-review ADR/audit rather than a fresh research document.
