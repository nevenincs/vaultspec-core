---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S28
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the vault status command with rollup and targeted modes, limit and since flags, advisory hints, and the versioned json envelope

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add the `vault status` command to `src/vaultspec_core/cli/vault_cmd.py`: no argument renders the rollup, an optional `TARGET` argument renders the grounding trace (decision D1).
- Wire `--limit` (default 10), `--since`, `--json`, `--no-hints`, and the shared `--target/-t` option via `TargetOption` and `apply_target`, matching sibling verbs (decision D4).
- Build one `VaultGraph` and pass it to both `compute_rollup` and `compute_trace`, so the data layer never rebuilds it.
- Render the rollup ordered in-flight plans first (open/closed counts, completion percent, modified), then recent changes grouped by type, then active features, then totals, as stems only with no absolute paths or graph structures (decision D7).
- Render the trace per plan: step display path, open/closed glyph, record stem or `no record` or `unlinked`, then grounding stems grouped by type (decision D5).
- Emit advisory hints through a status-local helper mirroring `emit_next_step_hint`: the rollup points at the targeted mode and `spec doctor`; the trace points at `vault graph --feature` and `vault plan status`. Honor `--no-hints` and `VAULTSPEC_NO_HINTS`.
- Emit `json_envelope("vault.status", ...)` schema v1 with `unchanged` status, dataclass-shaped data, and the same hints carried under `next_steps`.
- Map `TargetResolutionError` to exit 1 with a one-line message that names near-matches.
- Regenerate the generator-owned CLI reference regions in `src/vaultspec_core/builtins/reference/cli.md` and `docs/CLI.md`.

## Outcome

The verb is live in both modes. The rollup, trace, and JSON outputs were exercised against this repo's own vault. The language-contract, reference-drift, and full CLI test suites pass. Ruff format/check and ty are clean on the changed module.

## Notes

The CLI-reference regeneration here is the mechanical gate-keeper for the `CLI reference up to date` pre-commit hook; W03.P08.S34 covers the reference prose polish and overlaps this regeneration. No hand-authored handbook section was required: the handbook-drift test is satisfied by the generator's signature block alone.
