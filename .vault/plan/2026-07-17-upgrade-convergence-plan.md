---
tags:
  - '#plan'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-17-upgrade-convergence-adr]]'
  - '[[2026-07-17-upgrade-convergence-research]]'
---

# `upgrade-convergence` plan

## Steps

### Phase `P01` - branch and convergence engine

Open the tracking PR and land the fingerprint-verified refresh path in the managed-entry merge with its narrated per-entry messaging, plus the widened companion seam.

- [x] `P01.S01` - Open feature branch and draft PR referencing the convergence mandate and the governing decision; `repo workflow`.
- [x] `P01.S02` - Add fingerprint-verified refresh to the managed-entry merge with old-to-new narrated warning lines and a refresh item label; `src/vaultspec_core/core/mcps.py`.
- [x] `P01.S03` - Widen the upgrade mode-flip force seam from core-only to every package declared in the workspace map; `src/vaultspec_core/core/commands.py`.
- [ ] `P01.S04` - Cover untouched-entry refresh, hand-edited preservation, name-only legacy sidecar, and companion seam with real-workspace tests; `src/vaultspec_core/tests/cli`.

### Phase `P02` - migration and advisories

Register the versioned convergence migration riding the refresh path, and add the two warn-only doctor advisories for the holes core cannot fix.

- [ ] `P02.S05` - Register the launch-shape convergence migration invoking mcp_sync per enrolled provider, idempotent against the refresh path; `src/vaultspec_core/migrations`.
- [ ] `P02.S06` - Add warn-only doctor advisories for unrefreshable prek.toml hooks and stale static companion seeds with remediation hints; `src/vaultspec_core/core/diagnosis`.
- [ ] `P02.S07` - Cover migration idempotence on both modes and both advisories with real-workspace tests; `src/vaultspec_core/tests`.

### Phase `P03` - messaging, docs, and gates

Reconcile every user-facing hint and document with the now-truthful convergence behavior, then run the full gate set through review to a ready PR.

- [ ] `P03.S08` - Reconcile doctor hints, sync summaries, and the MCP doc convergence passage with the automatic behavior, exceptions, and opt-outs; `docs/MCP.md`.
- [ ] `P03.S09` - Run gates, dispatch code review, resolve findings, append audit entries, dogfood convergence on this workspace, finalize PR; `quality gates`.

## Description

Execute 2026-07-17-upgrade-convergence-adr: vaultspec-owned launch
artifacts converge automatically to the mandated standard on the next
upgrade, sync, or vault verb, narrated in user-facing output. P01 lands
the engine: the fingerprint-verified refresh path in the managed-entry
merge (B1) and the companion-wide upgrade seam (B3). P02 makes convergence
reach every legacy workspace regardless of flags via the registered
migration (B2) and adds the two warn-only advisories for what core cannot
fix (B5). P03 reconciles every hint and document with the now-truthful
behavior (B4) and gates the set. Ownership discipline is untouched
throughout: hand-edited and external entries never converge without
explicit force.

## Parallelization

Phases are sequential: the P02 migration rides the refresh path P01
lands, and P03 documents behavior only after it exists. Within P01, S02
and S03 are independent edits with S04 last; within P02, S05 and S06 are
independent with S07 last.

## Verification

- On a real workspace carrying the pre-guard legacy launch, a plain
  `sync` and a bare `install --upgrade` each rewrite the managed entries
  to the guarded shape, print the old and new command per entry with the
  reason, and leave hand-edited and external entries untouched.
- A workspace below the migration's target version converges on its first
  vault verb with no flags; re-running the migration is a no-op.
- The doctor's remediation hints match what the commands actually do; the
  two new advisories fire on real prek.toml and stale-seed fixtures and
  stay warn-only.
- No mocks, stubs, skips, or patches; prek clean; ty clean on changed
  files; the CI-matching unit gate and the repo-root suite green; code
  review dispatched and findings resolved; audit appended; convergence
  dogfooded on this workspace; PR ready.
