---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S03'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# implement the consolidated boundary predicate: prek.toml existence plus a mode-aware canonical-hook content check via tomllib, comparing entries resolved through canonical_hook_entries_for_mode, treating an unparseable prek.toml conservatively as hooks-absent

## Scope

- `src/vaultspec_core/core/prek_boundary.py`

## Description

- Add the prek boundary module owning the boundary invariant
- Implement PrekBoundaryState (config_exists, parse_error, hook_ids_present, entries_canonical) with owns_boundary and hooks_present views
- Implement collect_prek_boundary: tomllib read of prek.toml, local-repo hook extraction, mode-aware canonical-entry comparison via canonical_hook_entries_for_mode, parse errors reported conservatively as hooks-absent

## Outcome

Consolidated predicate landed in `src/vaultspec_core/core/prek_boundary.py`; no code path outside it performs a bare prek.toml existence check anymore.
