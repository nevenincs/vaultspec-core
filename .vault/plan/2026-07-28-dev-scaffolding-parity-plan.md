---
tags:
  - '#plan'
  - '#dev-scaffolding-parity'
date: '2026-07-28'
modified: '2026-07-30'
tier: L3
related:
  - '[[2026-07-28-dev-scaffolding-parity-adr]]'
  - '[[2026-07-28-dev-scaffolding-parity-rag-aeat-toolchain-survey-research]]'
---

# `dev-scaffolding-parity` plan

## Wave `W01` - split the oversized modules

Break the twelve production modules over 1000 lines into cohesive units, starting with the four over 1500. Every later Wave depends on this one: extraction redistributes functions, so complexity hotspots ranked before the split may not survive it. Authorized by 2026-07-28-dev-scaffolding-parity-adr.

### Phase `W01.P01` - extract the four modules over 1500 lines

Split the four largest production modules into cohesive units and lower the module-length ceiling to the new worst.

- [x] `W01.P01.S01` - Extract the spec command module into cohesive units; `src/vaultspec_core/cli/spec_cmd.py`.
- [x] `W01.P01.S02` - Extract the vault command module into cohesive units; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `W01.P01.S03` - Extract the core commands module along its install and sync seams; `src/vaultspec_core/core/commands.py`.
- [x] `W01.P01.S04` - Extract the graph api module into query and rendering units; `src/vaultspec_core/graph/api.py`.
- [x] `W01.P01.S05` - Lower the module-length ceiling to the post-extraction worst and regenerate its census; `pyproject.toml`.

### Phase `W01.P02` - extract the eight modules over 1000 lines

Bring the remaining four-figure modules under 1000 lines and ratchet the ceiling again.

- [x] `W01.P02.S06` - Bring the remaining eight production modules under one thousand lines; `src/vaultspec_core`.
- [x] `W01.P02.S07` - Ratchet the module-length ceiling again and regenerate its census; `pyproject.toml`.

## Wave `W02` - pay down the per-function complexity hotspots

Reduce cognitive and cyclomatic complexity toward the tool defaults of 15 and 10, working the ranked offender list the health report produces after W01 has redistributed the largest modules. Feeds W03 by shrinking the functions that must then be annotated. Authorized by 2026-07-28-dev-scaffolding-parity-adr.

### Phase `W02.P03` - flatten the functions above cognitive 30

Extract the 57 functions scoring above 30 and lower the cognitive ceiling toward 25.

- [x] `W02.P03.S08` - Flatten the fifty-seven production functions scoring above cognitive thirty; `src/vaultspec_core`.
- [x] `W02.P03.S09` - Lower the cognitive-complexity ceiling toward twenty-five and regenerate its census; `pyproject.toml`.

### Phase `W02.P04` - close the ruff function-size gap

Bring statements, branches, returns, and arguments down toward ruff's own defaults.

- [x] `W02.P04.S10` - Reduce the worst statement branch return and argument counts toward the ruff defaults; `src/vaultspec_core`.
- [x] `W02.P04.S11` - Lower the mccabe and function-size ceilings and regenerate their census; `pyproject.toml`.

## Wave `W03` - close the strict-typing burndown

Annotate the codebase until basedpyright strict reports zero, then promote the dimension from advisory to gating by deleting the continue-on-error key in CI. Runs last because annotating a function that W01 or W02 is about to move or split is wasted work. Authorized by 2026-07-28-dev-scaffolding-parity-adr.

### Phase `W03.P05` - annotate the five dominant strict-typing rules

Clear the 7950 errors concentrated in the five reportUnknown/reportMissing rules.

- [x] `W03.P05.S12` - Annotate the parameters the missing-parameter-type rule reports; `src/vaultspec_core`.
- [x] `W03.P05.S13` - Resolve the unknown member argument variable and parameter type errors; `src/vaultspec_core`.

### Phase `W03.P06` - promote strict typing to a gate

Resolve the residual tail, including the genuine possibly-unbound findings, then make the dimension gating.

- [x] `W03.P06.S14` - Resolve the possibly-unbound and attribute-access findings which can denote real defects; `src/vaultspec_core`.
- [x] `W03.P06.S15` - Promote strict typing to a gate by removing its continue-on-error key; `.github/workflows/ci.yml`.

## Description

The gates themselves are landed and green. `2026-07-28-dev-scaffolding-parity-adr`
chose baseline calibration precisely so they could land green, which means every
threshold currently sits at this tree's worst offender rather than at a bar worth
holding. This plan is the burndown that turns the floor into a bar; the distance
to cover per dimension is the census in
`2026-07-28-dev-scaffolding-parity-rag-aeat-toolchain-survey-research`.

One ADR governs the whole plan. The Waves are ordered by the ratio of risk
removed to code disturbed: structural extraction of the largest modules first,
because every later dimension improves as a side effect of it; then the
per-function complexity hotspots; then the annotation debt, which is the largest
count but the lowest risk per change.

Every Step in this plan closes by lowering the corresponding threshold in
`pyproject.toml` in the same change. A Step that pays down a hotspot without
lowering the ceiling has reopened the headroom for the next regression and is
not complete.

## Steps

## Parallelization

The Waves are strictly sequenced, and the ordering is load-bearing rather than
conventional. Splitting an oversized module redistributes its functions, so
measuring per-function complexity before that split ranks hotspots that will not
exist afterwards. Annotating a function that is about to be extracted wastes the
annotation.

Within a Wave, Steps that name disjoint modules parallelize freely and are the
natural unit for a dispatched executor. Steps naming the same module must
serialize: these are large files and concurrent extraction produces conflicts
that are expensive to resolve correctly.

One hard constraint cuts across every Wave: only one agent may hold
`pyproject.toml` at a time, because every Step closes by editing a threshold in
it. Batch the threshold edits at the end of each Phase rather than per Step.

## Verification

- Every Step closed, and for each, the corresponding threshold in
  `pyproject.toml` lowered in the same change with its census comment
  regenerated by `just health census`.
- `just lint all` green, plus `just lint complexity`, `just lint nesting`, and
  `just lint size` green, at the reduced thresholds.
- `just test broad` green on Linux and Windows; these Waves touch install, sync,
  and CLI paths where platform behaviour differs.
- No threshold anywhere in `pyproject.toml` higher than the value this plan
  started from. A raised ceiling is a failed Step, not a tradeoff.
- Wave `W03` additionally requires the strict-typing step in
  `.github/workflows/ci.yml` to have its `continue-on-error` key deleted, which
  is what promotes the dimension from advisory to gating.
- `vaultspec-code-review` sign-off on each Wave before the next begins.
