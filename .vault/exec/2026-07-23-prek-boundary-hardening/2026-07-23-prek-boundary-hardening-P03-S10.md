---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S10'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# implement the prek.toml hook renderer: emit the mode-resolved canonical_precommit_hooks_for_mode set as a delimited managed text block in the verified local-system-hook TOML shape, appended or replaced without round-tripping operator-authored TOML

## Scope

- `src/vaultspec_core/core/prek_boundary.py`

## Description

- Implement render_prek_hook_block: canonical_precommit_hooks_for_mode rendered as repos/repos.hooks array-of-tables inside vaultspec-managed markers, in the shape verified against prek 0.4.10
- Implement the minimal TOML value renderer (strings, booleans, string lists) - no round-trip TOML writer, operator-authored content is never parsed for writing

## Outcome

Files: `src/vaultspec_core/core/prek_boundary.py`
