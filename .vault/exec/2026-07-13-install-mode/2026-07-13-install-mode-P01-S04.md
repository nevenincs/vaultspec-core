---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S04'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests covering workspace.json round trip, missing-file default, corrupted JSON, and malformed mode value handling

## Scope

- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add `test_workspace_mode` with WorkspaceFactory-based, real-filesystem tests
  for the committed declaration surface (no mocks, stubs, or skips).
- Cover round trips: tool mode, dependency mode with a floor version, the floor
  key omitted when unset, canonical output (sorted keys, trailing newline), and
  the forced schema version.
- Cover the missing-file lenient path returning `None`.
- Cover the strict paths: corrupt JSON, a non-object payload, a malformed mode
  value, and a missing `install_mode` key each raising `VaultSpecError` with the
  expected message.

## Outcome

Ten tests pass and the module lints clean. The suite pins the ADR Q1 read
contract behaviorally: a missing declaration is `None`, while any present-but-
broken declaration refuses loudly rather than resolving to a silent default. The
canonical-write assertion locks the deterministic committed-file shape so the
declaration diffs cleanly across contributors.

## Notes

No incidents. Used the shared `factory` fixture for a clean workspace root;
corrupt and malformed cases write raw bytes directly under `.vaultspec/` to
exercise the real read path. This module is the home for the P02
`resolve_install_mode` precedence and detection tests added later.
