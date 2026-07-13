---
tags:
  - '#plan'
  - '#bundled-cli-reference'
date: '2026-05-18'
modified: '2026-06-13'
tier: L1
related:
  - '[[2026-05-18-bundled-cli-reference-adr]]'
  - '[[2026-05-18-bundled-cli-reference-research]]'
---

# `bundled-cli-reference` plan: `bundle a machine-facing CLI reference and guard it against drift`

- [x] `S01` - author the machine-facing CLI reference as plain markdown covering the full command and subcommand inventory, per-command options with short forms, argument enumerations, exit-code semantics, and the environment-variable table, extracted from the machine-actionable surface of `docs/CLI.md`; `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `S02` - add a drift test that walks the live Typer command tree and asserts every command name and every non-global option appears in the bundled reference, mirroring the existing handbook drift test; `src/vaultspec_core/tests/cli/test_cli_reference_drift.py`.
- [x] `S03` - add a line to the references section pointing at the local seeded path `.vaultspec/rules/reference/cli.md` so an agent in a consumer project finds the reference without a network round-trip; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
