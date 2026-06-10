---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S06
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add archive-resolution branch tests covering link resolution against the archive directory

## Scope

- `src/vaultspec_core/graph/tests/test_graph.py`

## Description

- Added `_make_vault_with_archive` helper in `src/vaultspec_core/graph/tests/test_graph.py` that constructs a minimal two-document vault (source in `.vault/adr/`, archived target in `.vault/_archive/adr/`) on a `tmp_path` fixture.
- Added `TestVaultGraphArchiveResolution` with 9 tests covering: archived link absent from dangling list, phantom node created for archived target, `source-doc.out_links` resolves to qualified archive key, `_is_archived` True for bare stem, `_is_archived` True for qualified key, `_is_archived` False when no archive dir, `_is_archived` False for nonexistent stem, `_resolve_link` returning the qualified key, and directed edge existing in digraph.
- No mocks; all tests exercise real filesystem traversal.

## Outcome

9 new archive-resolution tests pass. The `_is_archived` and `_resolve_link` archive branch code paths are now covered end-to-end. Total graph test count: 78.

## Notes

No incidents. The `tmp_path` fixture provides isolation; each test builds its own vault.
