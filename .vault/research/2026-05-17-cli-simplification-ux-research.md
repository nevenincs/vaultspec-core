---
tags:
  - '#research'
  - '#cli-simplification-ux'
date: '2026-05-17'
modified: '2026-06-13'
related: []
---

# `cli-simplification-ux` research: `CLI simplification and UX hardening — scope and approach`

Scope and approach note for the CLI simplification and UX hardening initiative.
Tracking issue: GitHub #113. This document is a living scratchpad while the
audit is in progress and will be reshaped into a proper plan / ADR pair once
the surface is mapped.

## Findings

### Recurring agent-facing pain points

- `install` versus `sync` are routinely conflated. Agents reach for `install`
  when `sync` is meant, or fire `install` against a workspace that has already
  been provisioned, with side-effects that are not obviously bounded.
- Command discoverability is poor: the surface is wide (`install`,
  `uninstall`, `sync`, plus `vault`, `spec`, `migrations` subtrees) and there
  is no single in-CLI "what should I run right now?" affordance.
- Outcome feedback is inconsistent: some commands print success-looking output
  when they took partial or no action, others stay silent when a confirmation
  would prevent re-runs, and the vocabulary around `synced`, `installed`,
  `drifted`, `applied`, `repaired` is not normalised across surfaces.
- A few flows are quietly destructive: they can overwrite or remove on-disk
  artifacts without an obvious dry-run, diff-first, or "this is what I am
  about to do" preamble.

### Prior work to mine

- `.vault/plan/2026-03-27-cli-ambiguous-states-plan.md`
- `.vault/plan/2026-03-28-cli-ambiguous-states-audit-fixes-plan.md`
- `.vault/plan/2026-05-15-operator-cli-repair-pipeline-plan.md`
- Adjacent open issues: GitHub #108, #109, #111.

## Approach

1. Audit the full top-level command surface and the major subtrees against the
   three failure modes above. Collect concrete agent-transcript evidence in
   the sandbox harness.
1. Define a normalised outcome-state vocabulary (for example: `installed`,
   `unchanged`, `synced`, `drifted`, `repaired`, `skipped`) and one canonical
   way to render each one. Apply consistently across surfaces.
1. Tighten the `install` / `sync` / `uninstall` semantics so each command has
   one job, with state-aware refusals and guidance when run in the wrong
   state.
1. Add discoverability affordances: a top-level "what to run next" entry
   point, clearer `--help` summaries, and a machine-readable index of
   commands suitable for agent consumption.
1. Capture agent-facing transcripts as fixtures so the UX feedback strings,
   not just exit codes, regress under test.

## Sandbox harness

A throwaway sandbox project named `harbor-notes` is used to drive end-to-end
CLI flows from a fresh workspace. It lives outside this repository on disk
during development and is not committed here. Reset by wiping and
re-initialising.

## Out of scope

- Public Python API changes to `vaultspec_core` modules.
- MCP server surface rework. May follow once the CLI vocabulary stabilises.
- Re-theming Rich output or large prose rewrites of the CLI reference beyond
  what the audit forces.
