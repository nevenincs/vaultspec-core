---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S22'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
  - "[[2026-07-09-firmware-mcp-primacy-audit]]"
---

# Perform the mandatory closeout code review of the full reworded firmware set, confirming per-surface primacy split, three-band honesty, byte-stable gateway catalog, and unchanged allowlists against the ADR constraints

## Scope

- `src/vaultspec_core/builtins`

## Description

- Ran the mandatory `vaultspec-code-reviewer` audit over the firmware reword (diff `1728af8..HEAD`) against the accepted ADR.
- Verified the per-surface split, three-band honesty, both-worlds correctness, persona allowlist safety, marker byte-stability, sync consistency, and standards.

## Outcome

Verdict PASS - no critical or high findings. All load-bearing constraints hold: rules and system prompt name MCP tools primary with a single CLI-fallback clause; personas stay capability-first with the CLI as the named mechanism and byte-identical `tools:` allowlists; band-2 and band-3 verbs are never implied MCP-native; the `vaultspec:generated` command-inventory block is byte-unchanged so the MCP gateway catalog is stable; standards clean and the CLI rule roughly halved. Two low, non-blocking notes: the reference dual-role paragraph was correctly placed in the generator-preserved prose zone of the emitted reference rather than in `reference_gen.py` (the ADR's stated mechanism rested on a mistaken premise about where the header prose lives), and a cosmetic curator list-wrap. Findings recorded in the linked audit.

## Notes

- The full-gate showed 4 pre-existing `TestAddSubcommand` failures unrelated to this feature: the CLI dates documents in UTC (`vault_cmd.py`) while those tests assert the local date, which diverges only in the local/UTC midnight window. They predate the session and are not a reword regression.
