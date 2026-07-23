---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S05'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# make collect_precommit_state content-aware through the predicate: emit UNREFRESHABLE only when prek.toml lacks the canonical hooks, add the new ORPHANED signal member for a stale co-present YAML when prek.toml is healthy, and handle ORPHANED in \_resolve_precommit as a no-op in the same change

## Scope

- `src/vaultspec_core/core/diagnosis/collectors.py`
- `src/vaultspec_core/core/diagnosis/signals.py`
- `src/vaultspec_core/core/resolver.py`

## Description

- Add the ORPHANED member to PrecommitSignal
- Rewrite collect_precommit_state around the boundary predicate: UNREFRESHABLE only when prek.toml lacks the canonical hooks; ORPHANED for a co-present YAML beside a healthy prek.toml; COMPLETE when hooks live in prek.toml with no YAML left
- Handle ORPHANED in \_resolve_precommit as a documented no-op in the same change, keeping the resolver exhaustive

## Outcome

Removes both the false positive (healthy transplant flagged UNREFRESHABLE) and the false negative (canonical YAML reported COMPLETE while prek ignores it). Files: `src/vaultspec_core/core/diagnosis/signals.py`, `src/vaultspec_core/core/diagnosis/collectors.py`, `src/vaultspec_core/core/resolver.py`
