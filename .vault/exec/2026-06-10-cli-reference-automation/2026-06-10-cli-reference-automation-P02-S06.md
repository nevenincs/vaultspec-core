---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S06
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# GATED on the ADR deciding build, document the generator as the canonical reference-update path in the CLI rule (D6 deferral)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Add a "Maintaining the bundled CLI reference" section to the bundled CLI rule source
  `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- Name `vaultspec-core spec reference generate` as the canonical way to update the
  bundled reference after a command, flag, or argument change.
- State the managed-region discipline: the zones between the `vaultspec:generated`
  markers are generator-owned and must never be hand-edited, while the surrounding prose
  stays hand-authored.
- Note that `--check` renders in memory, diffs against the committed file, exits non-zero
  on mismatch, is wired into pre-commit, and gates CI.
- Format the rule with `mdformat --wrap 88`.

## Outcome

The CLI rule now documents the generator as the canonical reference-update path and
records the generator-owned-region discipline, so an agent inheriting the rule learns not
to hand-edit the managed zones and to run the generator instead. The rule source change
is confined to the documentation section; no command tables or runtime guidance were
altered.

## Notes

The edit targets the package builtins rule source under
`src/vaultspec_core/builtins/rules/`, not a workspace `.vaultspec/` copy, so no
`vaultspec-core sync` propagation was run from this repository (the source repo does not
track `.vaultspec/`). The codification candidate the ADR named
(`generated-reference-is-cli-owned`) is a discretionary Phase-6 follow-up beyond this
step's scope and was not authored here.
