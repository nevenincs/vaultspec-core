---
tags:
  - '#plan'
  - '#status-hardening'
date: '2026-06-13'
modified: '2026-07-13'
tier: L3
related:
  - '[[2026-06-13-status-hardening-adr]]'
  - '[[2026-06-13-status-hardening-research]]'
  - '[[2026-06-12-vault-orientation-adr]]'
---

# `status-hardening` plan

Harden the orientation surface into a status discovery mini-framework: promote
`status` to a top-level verb, enrich every plan with a clean one-line overview
(level, open/completed waves, completed phase, next open step), resolve stems and
feature handles uniformly across the `vault plan` commands, surface a feature's exact
files with paths, fix recency hygiene, drop double-counted index docs, and move the
firmware to teach the new verb.

## Description

Implements the accepted status-hardening ADR (decisions H1 through H11) on the blind
testimonial research (findings F1 through F8). Wave one extends the batched status core
(predecessor D6) with per-wave / per-phase completion and the first-open-step cursor,
carried through the rollup data model (H2). Wave two builds the surfaces: it moves the
orientation verb to top-level `vaultspec-core status` and removes `vault status` (H1),
adds one reused clean no-glyph plan-line renderer used in the rollup and the trace
(H3), surfaces step check-state and a "you are here" cursor plus a recently-completed
section (H4, H5), exposes real document paths (H7), and drops index documents from
summaries (H8). Wave three promotes a shared plan-target resolver so stems and feature
handles resolve everywhere with a clean near-match error (H9), and bounds recency noise
(H6). Wave four rewrites the firmware orient-first mandate and command table to name
the top-level verb, regenerates the CLI-owned reference, closes the secondary gaps
(H11), and verifies the whole surface (H10). The predecessor invariants hold
throughout: read-only, no artifact, the graph stays an implementation detail, recency
stays the `modified:` stamp.

## Steps

## Wave `W01` - per-plan enrichment core

Extend the single batched status pass with the per-container completion and next-open-step
facts the surfaces render, with no new storage or traversal (decisions H2, H3; predecessor D6).

### Phase `W01.P01` - enrichment data core

Compute per-wave / per-phase completion and the first-open-step cursor inside the existing pass and carry them through the rollup model.

- [x] `W01.P01.S01` - expose per-wave and per-phase step membership on the parsed plan model so container completion is derivable without a rescan; `src/vaultspec_core/plan/parser.py`.
- [x] `W01.P01.S02` - extend PlanStatus with waves_completed, phases_completed, and next_open_step, computed in collect_status during the batched pass; `src/vaultspec_core/plan/status.py`.
- [x] `W01.P01.S03` - add the new fields to status_to_json_dict as an additive contract change; `src/vaultspec_core/plan/status.py`.
- [x] `W01.P01.S04` - carry waves_completed, phases_completed, and next_open_step through PlanInFlight and populate them in \_plans_in_flight; `src/vaultspec_core/vaultcore/orientation.py`.

### Phase `W01.P02` - enrichment core tests

Lock the enrichment behaviour against real plans across tiers.

- [x] `W01.P02.S05` - add factory-based tests for waves_completed, phases_completed, and next_open_step across L1 to L4 plans, including a fully complete plan (next_open_step is None); `src/vaultspec_core/tests/plan/test_status.py`.

## Wave `W02` - status surfaces

Move the verb to top-level, render the codified clean plan line in the rollup and the trace, surface
check-state and paths, and stop double-counting index documents (decisions H1, H3, H4, H5, H7, H8).

### Phase `W02.P03` - top-level status verb

Promote orientation to `vaultspec-core status` and remove the old nesting.

- [x] `W02.P03.S06` - register the top-level status [TARGET] command delegating to the orientation core (rollup with no target, grounding trace with a target), with --limit / --since / --json / --no-hints; `src/vaultspec_core/cli/root.py`.
- [x] `W02.P03.S07` - remove the vault status command and its registration; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `W02.P04` - clean plan-line renderer and rollup

Render the one reused clean no-glyph plan line and the recently-completed bucket.

- [x] `W02.P04.S08` - add a single shared clean plan-line renderer (column-aligned, no glyphs): feature, tier, W c/T, P c/T, k/N steps, percent, next display-path, with the condensed tier k/N percent tail variant; `src/vaultspec_core/cli/rendering.py`.
- [x] `W02.P04.S09` - render plans-in-flight rows with the full plan line and active-features rows with the condensed tail; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `W02.P04.S10` - add a recently-completed section (plans at 100% within the recency window, most recent first) and annotate the in-flight section with its open-step criterion; `src/vaultspec_core/vaultcore/orientation.py`.
- [x] `W02.P04.S11` - add rollup rendering tests covering the plan line, active-features tail, and recently-completed bucket; `src/vaultspec_core/tests/cli/test_vault_status.py`.

### Phase `W02.P05` - targeted trace

Make the trace self-sufficient: check-state, cursor, real paths, no index double-count.

- [x] `W02.P05.S12` - render the clean plan line as the trace header and show each step row with [x]/[ ] check-state and a cursor on the first open step; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `W02.P05.S13` - add a --paths human mode and a path field beside every stem in the trace JSON (step record paths, summaries, grounding docs), sourced from existing graph nodes without leaking the graph; `src/vaultspec_core/vaultcore/orientation.py`.
- [x] `W02.P05.S14` - exclude index documents from the recent-documents grouping, grounding grouping, and any document-count summary so a feature's docs are never double-counted; `src/vaultspec_core/vaultcore/orientation.py`.
- [x] `W02.P05.S15` - add trace tests for check-state, the open-step cursor, --paths / JSON paths, and index exclusion; `src/vaultspec_core/tests/cli/test_vault_status.py`.

## Wave `W03` - target resolution and recency hygiene

Promote a shared plan-target resolver so stems and feature handles resolve across every plan command
with a clean error, and bound recency output noise (decisions H6, H9).

### Phase `W03.P06` - shared plan-target resolver

One resolver, the orientation verb's near-match error contract.

- [x] `W03.P06.S16` - add a shared plan-target resolver accepting a literal path, stem, stem.md, feature name, or #feature tag and resolving a handle to the feature's single plan, raising the orientation near-match error (never a raw traceback) on failure; `src/vaultspec_core/cli/_target.py`.
- [x] `W03.P06.S17` - add resolver tests for every accepted form plus ambiguous and unknown inputs and their near-match messages; `src/vaultspec_core/tests/cli/test_plan_target.py`.

### Phase `W03.P07` - wire plan commands to the resolver

End the asymmetry: every `vault plan` command accepts what the orientation verb accepts.

- [x] `W03.P07.S18` - resolve the PATH argument of vault plan status and vault plan check through the shared resolver; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `W03.P07.S19` - resolve the PATH argument of vault plan query through the shared resolver and add a --target option; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `W03.P07.S20` - resolve vault plan step / phase / wave / tier / epic targets and convert resolution failures into the user-facing error contract instead of a swallowed traceback; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `W03.P07.S21` - add tests asserting every vault plan command accepts stem and feature-handle targets and rejects unknown ones cleanly; `src/vaultspec_core/tests/cli/test_plan_target.py`.

### Phase `W03.P08` - recency hygiene

Make `--limit` honest and stop exec from flooding the view.

- [x] `W03.P08.S22` - apply --limit uniformly to every document-type group, collapse the exec group to one line per feature by default, and add a --verbose-exec flag to restore per-record rows; `src/vaultspec_core/vaultcore/orientation.py`.
- [x] `W03.P08.S23` - add recency tests for the uniform cap, exec collapse, --verbose-exec, and the --since window; `src/vaultspec_core/tests/cli/test_vault_status.py`.

## Wave `W04` - firmware, reference, secondary gaps, and verification

Move the firmware to teach the top-level verb, regenerate the CLI-owned reference, close the
secondary gaps, and verify the whole surface (decisions H10, H11; firmware-reference-parity).

### Phase `W04.P09` - firmware and generated reference

Land the verb's firmware mandate and reference in the same change that ships it.

- [x] `W04.P09.S24` - rewrite the orient-first mandate to name `vaultspec-core status` and its targeted form; `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `W04.P09.S25` - rewrite the zeroth-move prose and the command table row to the top-level status verb; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.
- [x] `W04.P09.S26` - regenerate the CLI-owned reference so the status signature and section reflect the top-level verb; `src/vaultspec_core/builtins/reference/cli.md`.

### Phase `W04.P10` - secondary gaps

Close the testimonial's secondary findings (F7).

- [x] `W04.P10.S27` - emit a graceful error naming the missing .vaultspec/ directory and suggesting --target or the nearest vault instead of a bare failure; `src/vaultspec_core/cli/_target.py`.
- [x] `W04.P10.S28` - add a latest_activity column (human and JSON) and a --stale-days filter to vault feature list; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `W04.P10.S29` - append a !n flag to the plan line when exec_missing_ids is non-empty so checked-but-ungrounded steps are distinct from open steps; `src/vaultspec_core/cli/rendering.py`.

### Phase `W04.P11` - verification

Migrate the suite to the new verb and prove the surface green.

- [x] `W04.P11.S30` - migrate all tests and fixtures referencing vault status to the top-level status verb and add a firmware-reference-parity assertion for the verb name; `src/vaultspec_core/tests`.
- [x] `W04.P11.S31` - run the full test suite, ty, and prek to green and smoke-test status rollup, targeted trace, and plan-handle resolution end to end; `repository root`.
