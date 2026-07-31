---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:5fe037687ab976fa10ea16f0be9eb272c261bfc49c8b4a2d53dd6e1c37099241'
step_id: 'S04'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# route the \_scaffold_precommit short-circuit through the boundary predicate, replacing its bare existence check

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Replace the bare prek.toml existence check in \_scaffold_precommit with collect_prek_boundary
- Split the short-circuit logging: healthy info when hooks already live in prek.toml, stranded warning naming spec precommit migrate otherwise
- Update the scaffold docstring to the verified exclusive-read contract

## Outcome

Files: `src/vaultspec_core/core/commands.py`
