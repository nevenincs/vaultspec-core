---
tags:
  - '#audit'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# `firmware-mcp-primacy` audit: `firmware reword MCP-primacy fidelity`

## Scope

Mandatory code review (plan step S22) of the firmware reword across P01-P05 on branch `feature/mcp`, diff range `1728af8..HEAD`. This is a prose/firmware change, so the audit targets correctness-of-wording and constraint-fidelity against the accepted ADR, not runtime behavior. Surfaces reviewed: the two rules (`vaultspec-cli.builtin.md`, `vaultspec.builtin.md`), the system prompt fragment `system/03-vaultspec.md`, five reworded personas (`vaultspec-writer`, three executors, `vaultspec-docs-curator`), the reference header (`reference/cli.md`), the generator `reference_gen.py`, and the `.vaultspec/` plus `.claude/` provider-synced copies. Verdict: PASS - no critical or high findings; two low items, both benign.

## Findings

### three-band-factual-fidelity | none | No firmware text implies MCP coverage for band-2 or band-3 verbs

The three-band honesty scheme (ADR Q6) is faithfully rendered. `rules/vaultspec-cli.builtin.md` bands `sync`, `spec <resource> sync`, and the above-Step plan verbs (`tier promote/demote`, `wave`, `phase`, `epic intent`) as gateway-only/CLI-first with the correct `invoke`-destructive-annotation justification, and bands `vault feature index`, `spec mcps add/remove/sync`, `uninstall` as CLI-only. The feature-index mandate is correctly reworded to side-effect-plus-manual-CLI in all three locations (`rules/vaultspec.builtin.md` twice, `system/03-vaultspec.md`). No location says "use the MCP" to regenerate the index or implies hot-tool status for a gateway-only verb. The nine-tool list matches the tool-schema decision exactly.

### both-worlds-correctness | none | Every hot-path mandate carries a reachable CLI fallback with no availability conditional

Every reworded mandate is true whether or not the MCP is connected. The Mandate states MCP-primary-CLI-otherwise; the file-level fallback clause generalizes the discovery-rule pattern. The system-prompt plan paragraph names `plan_progress`/`plan_edit` primary and gives the complete `vaultspec-core vault plan ...` CLI path for above-Step changes and disconnected sessions. No conditional-on-connection logic appears anywhere - degradation is by declarative wording alone, per ADR Q2.

### persona-safety | none | Allowlists byte-identical, exact CLI verb retained, toggle dropped, MUST invariants survive

No persona `tools:` line appears in the diff for any of the five reworded personas; `mcps/vaultspec-core.builtin.json` is not in the changeset. No persona is steered to an MCP tool its allowlist excludes - all keep the CLI as the named mechanism. The owning-verb MUST invariants survive. `toggle` was dropped from all three executors (verified absent in both the diff and the provider copy).

### marker-byte-stability | none | Command-inventory block byte-identical; only additive prose above markers

Byte comparison from the `vaultspec:generated:begin command-inventory` marker to EOF is identical between `1728af8` and HEAD in `builtins/reference/cli.md`; the `.vaultspec/` copy carries the same additive hunk. The change is purely one new paragraph above the markers. The drift test guards the marker region, which is unchanged.

### sync-consistency | none | .vaultspec and .claude copies carry the reword; no registration change

The `.vaultspec/` hunks are identical to the `builtins/` sources. Provider `.claude/` copies contain the reworded content and differ from `builtins/` only by expected provider frontmatter rendering, not by missing content. The MCP registration JSON is untouched.

### standards | none | No dashes, CLI rule roughly halved, no new AI phrasing

No em or en dashes in any changed builtin (spaced hyphens throughout). `rules/vaultspec-cli.builtin.md` went 116 to 67 lines, meeting "roughly half". Wording is capability-first and concise. No new "AI" phrasing was introduced by the reword; the pre-existing "AI agents" phrase in the reference header is unchanged and out of scope.

### reference-gen-mechanism-deviation | low | The header paragraph was placed directly in the emitted reference files, not in the generator source, which is the architecturally correct path

ADR Q5 and the Implementation list instruct that the dual-role header paragraph be edited "at its source in the reference generator, not in the emitted file", naming `reference_gen.py` as a changing file. In fact `reference_gen.py` is unchanged, and the paragraph was added directly to the emitted `builtins/reference/cli.md` and `.vaultspec/reference/cli.md`. This is not a defect: the generator's own contract is that it preserves hand-written prose zones verbatim and rewrites only content between markers. The header above the markers is a preserved prose zone, not generator-emitted output - there is no header-prose literal in the generator to edit. So a future `spec reference generate` preserves the hand-added paragraph and the drift test stays green. The executor achieved the ADR's actual goal via the correct mechanism; the ADR's stated mechanism rested on a mistaken premise about where the header prose lives. Recorded so the ADR is not later read as evidence of an unimplemented step.

### curator-graph-bullet-wrap | low | The docs-curator graph line wrap may read as a nested bullet

In `agents/vaultspec-docs-curator.md` the reworded graph line wraps with a 2-space-indented continuation that renders as intended prose under mdformat but visually resembles a spurious sub-bullet. Purely cosmetic; optional to reflow.

## Recommendations

Merge is safe: no critical or high findings. Status PASS. The reword is a faithful, honest implementation of the per-surface split - MCP-first-with-fallback on the rules and system prompt, capability-first with the CLI as the named mechanism on the personas, allowlists untouched, the three bands stated without overclaim, the marker block byte-stable, and standards clean. The two low items are non-blocking: the reference-gen mechanism note is recorded above (the header paragraph is correctly placed in a generator-preserved prose zone, so the "generator source" implementation line reads as satisfied rather than skipped), and the curator list-wrap is a cosmetic nit left for an optional future reflow.
