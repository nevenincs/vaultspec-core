---
tags:
  - '#plan'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
tier: L2
related:
  - '[[2026-07-16-firmware-code-boundary-adr]]'
  - '[[2026-07-16-firmware-code-boundary-research]]'
---

# `firmware-code-boundary` plan

## Description

This plan executes the firmware-code-boundary decision (see `related:`): a
documentation-only firmware pass introducing the one-way vault reference boundary -
`.vault/` and `.vaultspec/` are removable development scaffolding, code must stand on
its own, and tracked source-file content never references the project's own
development records. The ADR fixes the canonical mandate wording and the six target
surfaces; the grounding research fixes the insertion anchors. Phase P01 lands the
canonical statement on the always-on surfaces (core mandates, vaultspec system file,
vaultspec rule hierarchy). Phase P02 echoes it where code is written and gated (the
executor trio identically per the standing parallelism constraint, the code reviewer's
Intent Domain, the execute skill's Traceability line). Phase P03 propagates via
`vaultspec-core sync`, runs the gates, and registers the deferred mechanical
source-boundary checker as a GitHub follow-up issue. Git commit trailers and commit
messages are out of scope by decision; no Python, template, or persona-frontmatter
changes are permitted.

## Steps

### Phase `P01` - System and rules firmware

Land the canonical boundary mandate and its always-on echoes in the system prompt sources and the vaultspec rule.

- [x] `P01.S01` - Add the canonical Code-stands-alone mandate bullet (removable scaffolding, one-way reference direction, trailer carve-out) beside the Comments mandate; `src/vaultspec_core/builtins/system/01-core.md`.
- [x] `P01.S02` - Add the one-sentence removable-harness characterization with one-way reference direction where the .vault store is introduced; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P01.S03` - Add the one-clause hierarchy statement that source code sits outside the documentation hierarchy and never references vault or harness contents; `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.

### Phase `P02` - Personas and skills

Echo the boundary on the code-writing executor trio, the review gate, and the execute skill's Traceability line.

- [x] `P02.S04` - Add the byte-identical boundary bullet to the core implementation mandate of all three executor personas; `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`.
- [x] `P02.S05` - Add the Boundary integrity check to the Intent Domain, mapped to the existing HIGH severity class; `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`.
- [x] `P02.S06` - Disambiguate the Traceability requirement in place: mapping lives in the Step Record, never as annotations in code; `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`.

### Phase `P03` - Propagation and closeout

Sync the deployed mirror, run the validation gates, and register the mechanical-checker follow-up.

- [x] `P03.S07` - Propagate builtin edits to the deployed mirror with vaultspec-core sync and confirm spec doctor is clean; `.vaultspec/`.
- [x] `P03.S08` - Run vault check all, prek hooks, and the unit test gate, fixing any drift the gates surface; `src/vaultspec_core`.
- [x] `P03.S09` - Register the read-only vault check source-boundary scanner as a GitHub follow-up issue citing the governing decision; `gh issue`.

## Parallelization

P01 must land before P02 so the persona and skill echoes compress a canonical
statement that already exists rather than inventing their own wording. Within each of
P01 and P02 the Steps touch disjoint files and may run in parallel. P03 is strictly
sequential and last: sync (S07) requires all source edits committed, the gates (S08)
require the sync, and the follow-up issue (S09) closes out the feature.

## Verification

- The canonical mandate appears exactly once in full form (core mandates) and each
  echo surface carries one compressed clause; a grep for the boundary phrasing across
  `src/vaultspec_core/builtins/` matches only the six decided surfaces.
- The executor-trio bullet is byte-identical across the three persona files (diff of
  the extracted bullet is empty).
- No wording forbids the literal `.vault` path string, and the trailer carve-out
  sentence names commit trailers as the sanctioned channel.
- `vaultspec-core sync` reports the deployed mirror reconciled;
  `vaultspec-core spec doctor` and `vaultspec-core vault check all` are clean.
- prek hooks and the unit test gate (`pytest src/vaultspec_core -m unit`) pass.
- The follow-up issue for the mechanical source-boundary checker exists on GitHub and
  names the governing decision stem.
- Code review of the full diff passes; the plan is complete when every Step is closed.
