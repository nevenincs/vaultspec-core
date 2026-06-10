---
name: generated-reference-is-cli-owned
---

# Generated reference is CLI-owned: regenerate, never hand-edit the managed zones

A worked example of codification applied to an audit finding. Promoted from the CLI
reference automation audit following the discipline described in the `vaultspec-codify`
rule.

## Rule

The bundled CLI references' generator-managed regions - delimited by the
`vaultspec:generated:begin` and `vaultspec:generated:end` markers in
`src/vaultspec_core/builtins/reference/cli.md` and `docs/CLI.md` - are updated only by
running `vaultspec-core spec reference generate`, never by hand-editing inside the
markers; the `--check` mode gates pre-commit and CI and fails until both references
match fresh output.

## Why

The bundled reference is hand-authored prose wrapped around generator-owned zones, and
the hand-authored content drifted from the live Typer surface every time a flag or
enumeration changed. The `2026-06-10-cli-reference-automation-audit` documented that
drift (the prior reference omitted live signatures, D6) and that the two surfaces
drifted in ordering against each other (`GENREVIEW-003`, first divergence at index 7).
The generator plus `--check` is the durable guarantee: drift is mechanically corrected
and CI fails deterministically until the managed regions equal fresh output.

## How

- **Good:** a new flag lands on a verb; run `vaultspec-core spec reference generate`,
  review the regenerated managed region, and commit it. Both `cli.md` and `docs/CLI.md`
  inventories regenerate from one Typer walk and cannot diverge.

- **Bad:** hand-edit a signature or option table inside the
  `vaultspec:generated:begin/end` markers; the edit is overwritten on the next generate
  and `--check` fails CI in the meantime.

- Hand-written prose **outside** the markers (the entry-point table, global-options
  narrative, sync-vocabulary section, environment-variable table) is still
  hand-maintained normally; the generator reads but never rewrites those zones.

## Status

Active. The generator and its `--check` gate have shipped across both managed files. The
rule's intent (the managed zones are CLI-owned) is now structurally enforced; the
author's remaining duty is to regenerate rather than hand-edit inside the markers.

## Source

Audit `2026-06-10-cli-reference-automation-audit`, the generator design plus findings
`GENREVIEW-002` and `GENREVIEW-003`. Sibling decision ADR
`2026-06-10-cli-reference-automation-adr`.
