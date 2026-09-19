---
tags:
  - '#exec'
  - '#framework-dir-flatten'
date: '2026-06-25'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:f7f6d8fd8f3bc3f150cde964cc3f8d7bd87bfb34fc0a7bb7c6e1ac0dac226b37'
related:
  - "[[2026-06-25-framework-dir-flatten-plan]]"
---

# `framework-dir-flatten` ledger

## Changes

- `S01` `M` `src/vaultspec_core/core/types.py`
- `S02` `M` `src/vaultspec_core/core/commands.py`
- `S03` `M` `src/vaultspec_core/core/revert.py`
- `S04` `M` `src/vaultspec_core/vaultcore/hydration.py`
- `S05` `M` `src/vaultspec_core/vaultcore/checks/rename_integrity.py`
- `S06` `M` `src/vaultspec_core/core/resolver.py`
- `S07` `M` `src/vaultspec_core/builtins/__init__.py`
- `S08` `M` `src/vaultspec_core/core/rules.py`
- `S09` `M` `src/vaultspec_core/core/skills.py`
- `S10` `M` `src/vaultspec_core/core/system.py`
- `S11` `M` `src/vaultspec_core/core/agents.py`
- `S12` `M` `src/vaultspec_core/core/hooks.py`
- `S13` `M` `src/vaultspec_core/core/mcps.py`
- `S14` `M` `src/vaultspec_core/migrations/m_0_1_35_framework_flatten.py`
- `S15` `M` `src/vaultspec_core/migrations/__init__.py`
- `S16` `M` `src/vaultspec_core/migrations/tests/test_framework_flatten.py`
- `S17` `M` `src/vaultspec_core/tests/cli/conftest.py`
- `S18` `M` `src/vaultspec_core/protocol/tests/conftest.py`
- `S19` `M` `src/vaultspec_core/tests/cli/ sync cluster`
- `S20` `M` `src/vaultspec_core/tests/cli/`
- `S21` `M` `src/vaultspec_core/core/tests/`
- `S22` `M` `src/vaultspec_core/vaultcore/tests/`
- `S23` `M` `tests/`
- `S24` `M` `docs/framework.md`
- `S25` `M` `docs/MCP.md`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
