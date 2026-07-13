---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S31
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the vault status command row and the orientation bootstrap mandate

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Verify the live verb usage with `vaultspec-core vault status --help`; it accepts an
  optional `[TARGET]` argument.
- Add a Commands-table row mapping the orient-in-an-unknown-or-resumed-project task to
  `vaultspec-core vault status [TARGET]`.
- Add an Orientation paragraph immediately after the Mandate section describing the
  rollup, the targeted grounding trace, and the read-only zeroth-move framing.
- Reflow the file with mdformat at wrap 88.

## Outcome

The CLI rule in `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md` now names
the shipped `vaultspec-core vault status` verb in both the command table and a short
Orientation paragraph, satisfying ADR decision D8 and the firmware-reference-parity
rule now that the verb exists. The command row uses the bracketed `[TARGET]` token so
the language-contract suite treats it as a canonical invocation rather than a runnable
subcommand chain.

## Notes

None.
