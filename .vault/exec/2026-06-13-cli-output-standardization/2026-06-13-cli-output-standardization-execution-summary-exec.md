---
tags:
  - '#exec'
  - '#cli-output-standardization'
date: 2026-06-13
modified: 2026-06-13
related:
  - '[[2026-06-13-cli-output-standardization-plan]]'
  - '[[2026-06-13-cli-output-standardization-adr]]'
  - '[[2026-06-13-cli-output-standardization-research]]'
---

# cli-output-standardization exec summary

Executed the full L2 plan (27 of 27 steps closed) implementing the vaultspec CLI
output contract. The migration changes only the human text surface and leaves
every existing `--json` contract byte-identical; it closes the mutator `--json`
gaps onto the existing `Outcome` shape; and it pins the no-box and
width-determinism guarantees as tests. A `vaultspec-code-review` pass returned no
blocker, major, or minor findings and signed off the migration as safe to land.

## What landed

- **Shape vocabulary** (`cli/rendering.py`): the Record (`Field` /
  `render_record` / `record_as_json` / `emit_record`), Listing (`Column` / `Cell`
  / `render_listing` / `listing_as_json` / `emit_listing`), and box-free Tree
  (`TreeLine` / `render_tree`) shapes, plus the shared `truncate`, `summary_line`,
  and explicit empty-state helpers - each shape feeding one text renderer and one
  JSON renderer over a single payload, mirroring `OutcomeItem`.
- **spec surfaces** (`cli/spec_cmd.py`): rules / skills / agents / hooks / mcps
  list and status, `system show` (two listings), and the shared workspace
  `_render_diagnosis_table` migrated off Rich `Table` onto Record / Listing.
- **Remaining box constructs**: `config list` (`cli/config_cmd.py`), graph
  `--metrics` (`cli/vault_cmd.py`) onto Record; the graph default tree
  (`graph/api.py`) and the dry-run tree (`cli/rendering.py`) onto the box-free
  Tree; the install / uninstall `Panel` summaries onto box-free header lines.
- **Machine-surface gaps** (`cli/plan_cmd.py`): a `--json` Outcome surface added
  to every plan mutator (step / phase / wave / tier / epic) through the single
  `_save_plan_or_dry_run` chokepoint, with the error decorator made JSON-aware.
  `vault rule promote` and `vault adr supersede` already carried `--json`.
- **Contract test** (`tests/cli/test_output_contract.py`): byte-identical output
  across a 30-column and a 200-column environment, ASCII-only structure (the
  stdout-encoding half of the guarantee), and the absence of any box-drawing
  glyph in every shape and migrated helper.

## Verification

- Full src test suite green: 1691 (cli / graph / plan) plus 1704 (remaining src
  modules), and the new shape and contract tests (58 + 12).
- `ty` clean and `ruff` / `prek` (format, lint, CLI-reference, provider-artifact
  hooks) clean across every changed file.
- Live smoke tests: `spec rules list`, `config list`, and `vault graph` render
  box-free in text; `--json` surfaces emit the canonical envelope; a plan-mutator
  dry-run `--json` emits the mutation envelope and writes nothing. A
  Unicode-accurate scan of real `vault graph` output found zero box-drawing
  characters.

## Rollout method

Phase P01 (the shape vocabulary) and the `rendering.py` tree / panel rework were
authored directly; the per-file surface migrations (P02 spec, P03 config / graph)
and the repetitive plan-mutator `--json` threading (P04) were carried out by
scoped sub-agents over disjoint files, then reconciled, formatted, and reviewed.

## Notes

This feature shares the `feature/status-hardening` worktree with a separate,
concurrently developed `status-hardening` stream (top-level `status` verb, plan
resolver, orientation enrichment). The output contract is the rendering
foundation beneath it. The two streams touch `cli/vault_cmd.py` and
`cli/plan_cmd.py` in disjoint hunks; this migration's edits were kept to the
output-contract surfaces only. Nothing is committed; the streams remain
separable for review.
