---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S02'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add the WorkspaceDeclaration dataclass and read_workspace_declaration/write_workspace_declaration functions for the committed .vaultspec/workspace.json surface, including the minimum_vaultspec_version floor field

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add the `workspace_mode` module owning the committed `.vaultspec/workspace.json`
  declaration surface, distinct from the gitignored per-machine `providers.json`.
- Add the `WorkspaceDeclaration` dataclass carrying `install_mode`, the optional
  `minimum_vaultspec_version` floor field, and a forced `schema_version`.
- Add `read_workspace_declaration`: lenient on a missing file (returns `None`),
  strict on a broken one (corrupt JSON, non-object payload, or an
  out-of-vocabulary `install_mode` raises a typed `VaultSpecError`).
- Add `write_workspace_declaration`: canonical deterministic serialization
  (sorted keys, two-space indent, trailing newline, UTF-8), omitting the floor
  key when unset, wrapped in the shared advisory lock and atomic write.

## Outcome

The committed declaration is the team-shared source of truth the precedence
chain (P02) and the diagnosis checks (P04) read against. Confirmed the managed
gitignore block ignores only `providers.json`, snapshots, and lock sentinels
under `.vaultspec/`, so `workspace.json` commits cleanly for a teammate cloning
the project. Reads honor the ADR Q1 mandate: a missing declaration is simply
"no choice yet" while a present-but-malformed one refuses loudly rather than
resolving to a silent default. Module lands clean on `ruff check` and `ty check`.

## Notes

No incidents. Behavior is exercised by the round-trip, missing-file, corrupt-JSON,
and malformed-mode tests authored in S04.
