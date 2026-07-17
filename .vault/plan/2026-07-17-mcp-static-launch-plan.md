---
tags:
  - '#plan'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-17-mcp-static-launch-adr]]'
  - '[[2026-07-17-mcp-static-launch-research]]'
---

# `mcp-static-launch` plan

## Steps

### Phase `P01` - workspace recovery and branch

Restore this workspace to a working state (the incident left the venv without vaultspec-core) and open the feature branch and draft PR, so gates and dogfooding can run.

- [x] `P01.S01` - Open feature branch and draft PR referencing the venv-corruption incident and the ADR amendment; `repo workflow`.
- [x] `P01.S02` - Sweep orphaned MCP server processes holding venv DLLs and repair the venv with an explicit uv sync; `environment recovery`.
- [x] `P01.S03` - Refresh the stale exe-form vaultspec-rag seed via rag re-enrollment and verify both MCP servers complete an initialize handshake; `.vaultspec/mcps`.

### Phase `P02` - static launch render and legacy recognition

Amend the dependency-mode launch bytes with the no-sync guard through the single comparator and add the legacy-shape recognition that keeps doctor coverage honest on pre-refresh workspaces, with tests.

- [x] `P02.S04` - Add the no-sync guard to the dependency-mode branch of render_launch_for_mode and align its docstring with the static-execution contract; `src/vaultspec_core/core/mcps.py`.
- [ ] `P02.S05` - Recognize the legacy bare uv run module launch as DEPENDENCY in the observed-shape matcher with a drift hint pointing at sync --force or install --upgrade; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [ ] `P02.S06` - Update every launch-shape assertion and add legacy-shape and no-sync render tests across the renderer, per-package sync, collector, and mode-flip suites; `src/vaultspec_core/tests/cli`.

### Phase `P03` - documentation, sibling handoff, and gates

Document the static-execution contract, hand the rag-side contract off as a rag issue, and run the full gate set through review to a ready PR.

- [ ] `P03.S07` - Document the static-execution launch contract and refresh rendered-launch examples in the MCP doc and the CLI reference builtins source; `docs/MCP.md`.
- [ ] `P03.S08` - File the rag-side contract issue covering the tool-spec key and stale-seed refresh, referencing the shared launch-hygiene contract; `repo workflow`.
- [ ] `P03.S09` - Run gates, dispatch code review, resolve findings, append audit entries, dogfood the refreshed .mcp.json, finalize PR; `quality gates`.

## Description

Execute 2026-07-17-mcp-static-launch-adr: make every rendered MCP launch a
side-effect-free static execution. P01 restores this workspace (the incident
that motivated the record left the venv without vaultspec-core) and opens the
tracking PR. P02 lands the decision's core: the dependency-mode branch of the
single launch comparator gains the no-sync guard, the observed-shape matcher
learns the legacy bare-run shape so doctor coverage survives the migration
window, and every launch-shape assertion moves with the comparator. P03
states the contract in user documentation, hands the rag-side half (tool-spec
key, stale-seed refresh) to the sibling repository as an issue per the ADR's
A4 contract-only boundary, and gates the set. The in-flight mcp-stdio-lifetime
plan owns the server-lifetime tree; this plan touches only launch rendering,
diagnosis, tests, and docs.

## Parallelization

Phases are sequential: P02 needs the repaired environment from P01 to run
its suites, and P03 documents and gates what P02 built. Within P02, S04 and
S05 are independent edits that may interleave, with S06 last. Within P03,
S07 and S08 are independent; S09 closes.

## Verification

- A dependency-mode render emits the no-sync guard, byte-identically across
  the renderer, the convenience table, the doctor's candidates, and the
  synced provider configs; no test asserts the old shape.
- The legacy bare-run shape is recognized as DEPENDENCY by the matcher, is
  reported as drift with a working fix hint, and a sync --force or install
  --upgrade rewrites it to the guarded shape on a real workspace.
- Both MCP servers in this workspace complete a real initialize handshake
  over stdio after the refresh; repeated connects leave the venv byte-stable.
- prek clean on changed files; ty clean; the CI-matching unit gate and the
  MCP suites green; code review dispatched and findings resolved; audit
  appended; the rag issue filed and cross-referenced in the PR.
