---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S06'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
---

# Run prek, ty, and unit pytest gates, fix findings, finalize PR body and mark ready for review

## Scope

- `quality gates`

## Description

- Run the CI-matching unit gate: 1773 passed
- Run the full tests tree: 252 passed after repairing two latent, never-CI-run defects the sweep surfaced (stale context-budget suite pinning the pre-overhaul two-tool surface; a module basename collision breaking whole-tree collection)
- Run ruff and ty clean on every changed file; prek hooks passed on every commit
- Dispatch the code-reviewer persona: verdict PASS-with-notes; resolve the high fail-open gap and the medium argtypes finding, plus three lows, in a follow-up commit
- Update the PR body and mark ready for review

## Outcome

All gates green; review findings resolved and logged in the audit; PR 221
ready for review.

## Notes

Full-repo `ty check` reports nine pre-existing diagnostics (the pytest
temp-compat shim's deliberate monkeypatching and the dev-only statistic
sources); per-file ty passes on every file this branch touched. The
sibling vaultspec-rag fix proceeded in parallel in that repo under its own
records (its PR 228); the ADR's cross-repo wording was amended accordingly.
