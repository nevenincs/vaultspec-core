---
tags:
  - '#plan'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
tier: L2
related:
  - '[[2026-07-09-firmware-mcp-primacy-adr]]'
  - '[[2026-07-09-firmware-mcp-primacy-research]]'
---

# `firmware-mcp-primacy` plan

Reword the always-preloaded vaultspec-core firmware from CLI-mandating to per-surface MCP-first, dogfooded in this repo and shipped as a `sync`-propagated content change.

## Description

This plan implements the accepted `firmware-mcp-primacy` ADR: a per-surface reword of the firmware under `src/vaultspec_core/builtins/` that names the verified MCP tools as the primary transport where the surface addresses the orchestrating session, while keeping the CLI as the named mechanism where the surface addresses dispatched subagents. The always-on rules and the assembled system prompt go MCP-first-with-CLI-fallback; the ten personas stay capability-first with the CLI as their named mechanism and byte-identical `tools:` allowlists; the read-on-demand CLI reference becomes the explicit fallback-and-gateway catalog. No availability detection is introduced anywhere; correctness in both the MCP-connected and disconnected worlds is achieved by wording alone, modeled on the discovery rule's single trailing fallback clause.

The reword honors the ADR's three-band honesty scheme for operations without a first-class MCP tool: the hot seven are worded MCP-primary; the gateway-only verbs (`sync`, `spec <resource> sync`, plan `tier`, `wave`, `phase`, `epic intent`) are worded CLI-first with a single mention of the gateway; the denylisted verbs (`vault feature index`, `spec mcps` mutation, `uninstall`) are worded CLI-only. The feature-index mandate is reworded to index-as-`create`/`edit`-side-effect with the CLI verb as the manual path. The CLI rule is rewritten in place to roughly half its length; the CLI reference's generated command-inventory marker block stays byte-stable, with only its human-facing header prose changing, edited at the `reference_gen.py` generator source and regenerated so the drift test stays green. The change ships as an ordinary `sync`-propagated content edit with no schema migration, dogfooded first in this repo's own synced `.claude/rules/` copies. This plan writes no firmware edits; it is the execution scaffold for the ADR's file-by-file Implementation list.

## Steps

### Phase `P01` - Always-on rules

Rewrite the always-on CLI rule to transport-neutral MCP-first-with-fallback wording and apply the surgical plan-authority and feature-index touches to the framework rule, so the preloaded rule context names the hot MCP tools as primary while the CLI remains the single named fallback.

- [x] `P01.S01` - Rewrite the CLI rule in place: transport-neutral Mandate, nine-tool capability map, Q6 three-band CLI-or-gateway list, two-line CLI-fallback runtime block, single file-level fallback clause, and orientation and allowed-edits sections reworded to name the status and find tools as primary, targeting roughly half the current length; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [x] `P01.S02` - Apply the three surgical touches to the framework rule: adopt the Q4 after-form short shape for the plan-authority sentence and reword both feature-index mentions to index-as-side-effect with the CLI verb as the manual path, leaving taxonomy, hierarchy, and placeholder sections untouched; `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P01.S03` - Read the two reworded rule files through in both the MCP-connected and disconnected readings and confirm no conditional-availability logic, no false MCP coverage for denylisted verbs, and no hot-tool claim for gateway-only verbs; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.

### Phase `P02` - System prompt

Reword the assembled system prompt's orientation, feature-index, plan-authority, and subagent surfaces so the orchestrating session is steered to the status and plan MCP tools while the dispatched-subagent CLI-only reality is stated explicitly.

- [x] `P02.S04` - Reword the orient-first paragraph to name the status MCP tool as the primary orientation path with vaultspec-core status as the named fallback; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P02.S05` - Reword the feature-index sentence per Q6 to index-as-create/edit-side-effect with vaultspec-core vault feature index as the manual CLI path; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P02.S06` - Replace the MUST plan-verbs paragraph with the ADR Q4 after-form verbatim, keeping the owning-verb invariant in the MUST position and naming the plan_progress and plan_edit tools as primary with the CLI as the above-Step and disconnected-session path; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P02.S07` - Add the one-sentence Q3 subagent clause to the Agents section stating dispatched personas operate vaultspec through the CLI and MCP tools are not assumed inside subagents; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P02.S08` - Read the reworded system prompt file through in both the MCP-connected and disconnected readings and confirm the Q4 after-form is verbatim, the subagent clause is present, and no availability conditional was introduced; `src/vaultspec_core/builtins/system/03-vaultspec.md`.

### Phase `P03` - Agent personas

Reword the five write-capable personas to capability-first framing with the CLI retained as their named mechanism and byte-identical tools allowlists, dropping toggle from the executors' recommended set to match the tool surface's explicit-state stance.

- [x] `P03.S09` - Retitle the writer's CLI usage mandate to an owning-verbs mandate: invariant first, then the plan CLI verbs named once as this persona's execution path with the enumeration compressed to the verb-group list, leaving the tools allowlist byte-identical; `src/vaultspec_core/builtins/agents/vaultspec-writer.md`.
- [x] `P03.S10` - Reword the standard-executor Scaffold and step-state mandates to lead with the capability sentence while keeping the exact vault add exec and vault plan step check/uncheck verbs, dropping toggle from the recommended set, leaving the tools allowlist byte-identical; `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`.
- [x] `P03.S11` - Reword the low-executor Scaffold and step-state mandates to lead with the capability sentence while keeping the exact vault add exec and vault plan step check/uncheck verbs, dropping toggle from the recommended set, leaving the tools allowlist byte-identical; `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`.
- [x] `P03.S12` - Reword the high-executor Scaffold and step-state mandates to lead with the capability sentence while keeping the exact vault add exec and vault plan step check/uncheck verbs, dropping toggle from the recommended set, leaving the tools allowlist byte-identical; `src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`.
- [x] `P03.S13` - Apply the capability-first pass over the docs-curator's seven CLI references, retaining every verb and leaving the tools allowlist byte-identical; `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.
- [x] `P03.S14` - Diff each reworded persona against its prior version to confirm every tools allowlist is byte-identical, every exact CLI verb is retained, and toggle is dropped only from the three executors' recommended set; `src/vaultspec_core/builtins/agents/vaultspec-writer.md`.

### Phase `P04` - CLI reference dual-role

Add the dual-role header prose to the CLI reference at the generator source and regenerate, so the human-facing lookup gains its MCP-gateway-catalog framing while the generated marker block stays byte-stable and the drift test stays green.

- [x] `P04.S15` - Edit the emitted header prose at the reference generator source to add the Q5 dual-role paragraph naming the CLI-fallback lookup and MCP-gateway verb-existence roles, leaving the marker-block emission untouched; `src/vaultspec_core/cli/reference_gen.py`.
- [x] `P04.S16` - Regenerate the bundled CLI reference via vaultspec-core spec reference generate so the new header prose lands while the generated command-inventory marker block stays byte-identical; `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P04.S17` - Run test_committed_reference_is_in_sync_with_live_surface and confirm it stays green, proving only prose outside the markers changed; `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`.

### Phase `P05` - Sync and verification closeout

Propagate the reword into this repo's provider directories via sync and run the full verification suite, confirming vault check, the unit gate, the reference drift test, the byte-unchanged gateway catalog, and a mandatory code review before ship.

- [x] `P05.S18` - Run vaultspec-core sync to propagate the reworded builtins into this repo's .claude provider directories and read the sync result for created/updated/unchanged status with no failures; `.claude/rules/vaultspec-cli.builtin.md`.
- [x] `P05.S19` - Run vaultspec-core vault check all and confirm clean, regenerating the feature index if warned; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [x] `P05.S20` - Run the full unit gate pytest src/vaultspec_core -m unit and confirm it passes, catching any builtins-guarding test that the reword touched; `src/vaultspec_core/tests`.
- [x] `P05.S21` - Confirm the MCP gateway catalog is byte-unchanged by verifying the command-inventory marker block did not move, reading catalog.py parse against the regenerated reference; `src/vaultspec_core/mcp_server/catalog.py`.
- [ ] `P05.S22` - Perform the mandatory closeout code review of the full reworded firmware set, confirming per-surface primacy split, three-band honesty, byte-stable gateway catalog, and unchanged allowlists against the ADR constraints; `src/vaultspec_core/builtins`.

## Parallelization

The work is mostly independent prose edits that share a single worktree, so parallelism is real but bounded by file-level ordering, not by hard cross-Phase interdependencies. Phases P01, P02, and P03 touch disjoint files (`rules/`, `system/03-vaultspec.md`, `agents/`) and may run in parallel. Within P02 all five Steps edit the same `system/03-vaultspec.md` file, so S04 through S07 must serialize against each other; S08 is the read-through and runs after them. Within P03 the five persona edits (S09 through S13) touch five distinct files and may run in parallel, with S14 the diff review running after all of them. P04 carries hard internal ordering: S15 edits the generator source, S16 regenerates from it, and S17 runs the drift test, strictly in that order; P04 is otherwise independent of P01 through P03. P05 is the closeout and MUST run last, after every content Phase has landed: S18 sync, then S19 vault check, S20 the unit gate, and S21 the gateway-catalog byte check may run in parallel once sync completes, and S22 the mandatory code review runs last of all.

Agent assignment: `vaultspec-standard-executor` owns the content edits and verification runs (S01, S02, S04 through S07, S09, S10, S12, S13, S15 through S21); `vaultspec-low-executor` owns the mechanical low-executor persona edit (S11); `vaultspec-code-reviewer` owns the four safety-and-intent read-throughs and the closeout review (S03, S08, S14, S22).

## Verification

The plan is complete when every Step is closed (`- [x]`). Each content Phase pairs its edits with a verification, since there is little unit-testable surface in a prose reword: the verifiable criteria are (1) `vaultspec-core vault plan check` and `vaultspec-core vault check all --feature firmware-mcp-primacy` report clean; (2) the CLI rule is rewritten in place at roughly half its prior length with a transport-neutral mandate, the nine-tool capability map, the three-band CLI-or-gateway list, and a single file-level fallback clause; (3) the system prompt's MUST plan-verbs paragraph matches the ADR Q4 after-form verbatim and carries the one-sentence subagent clause; (4) every persona's `tools:` allowlist is byte-identical to its prior version and every exact CLI verb is retained, with `toggle` dropped only from the three executors' recommended set; (5) `test_committed_reference_is_in_sync_with_live_surface` stays green after regeneration, proving only prose outside the generated markers changed; (6) the MCP gateway command-inventory marker block is byte-unchanged so the `discover`/`invoke` catalog is identical before and after; (7) the full unit gate `pytest src/vaultspec_core -m unit` passes; (8) each reworded rule and system surface reads correctly in both the MCP-connected and the disconnected readings, with no availability-conditional logic anywhere; and (9) the mandatory `vaultspec-code-reviewer` closeout signs off against the ADR constraints.
