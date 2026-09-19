---
tags:
  - '#exec'
  - '#graph-hardening'
date: '2026-03-22'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:731eba8e8050c62fb2bd1519cef378f1fe7c5f04e016a096bc87686a23e03ec7'
related:
  - "[[2026-09-19-graph-hardening-plan]]"
---

# `graph-hardening` ledger

## Changes

- `S01` `M` `src/vaultspec_core/graph/api.py`
- `S01` `M` `src/vaultspec_core/graph/tests/test_graph.py`
- `S02` `M` `src/vaultspec_core/graph/api.py`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/references.py`
- `S03` `M` `src/vaultspec_core/graph/api.py`
- `S03` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S04` `A` `src/vaultspec_core/vaultcore/checks/dangling.py`
- `S04` `M` `src/vaultspec_core/vaultcore/checks/__init__.py`
- `S04` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S05` `M` `.pre-commit-config.yaml`
- `S05` `M` `src/vaultspec_core/vaultcore/checks/orphans.py`
- `S06` `M` `src/vaultspec_core/graph/tests/test_graph.py`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/tests/conftest.py`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/tests/__init__.py`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/tests/test_dangling.py`

## Notes

- `S01` Rows backfilled from the feature's historical execution records; this plan and ledger were reconstructed after execution, not logged contemporaneously.
