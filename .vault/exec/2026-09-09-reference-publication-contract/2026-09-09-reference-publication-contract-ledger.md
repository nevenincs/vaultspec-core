---
tags:
  - '#exec'
  - '#reference-publication-contract'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:38fa18f8ff25a8f7a7473524d2b4df597843b1ff5fa66c3b58fe05e94f6e10a5'
related:
  - "[[2026-09-09-reference-publication-contract-plan]]"
---

# `reference-publication-contract` ledger

## Changes

- `S01` `A` `src/vaultspec_core/cli/reference_surface.py`
- `S01` `M` `src/vaultspec_core/cli/reference_gen.py`
- `S01` `verify:` `just check-type-strict` -> `pass`
- `S02` `M` `src/vaultspec_core/cli/spec_cmd_reference.py`
- `S02` `A` `src/vaultspec_core/builtins/reference/published-surface.json`
- `S02` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S02` `M` `docs/CLI.md`
- `S02` `verify:` `pytest test_cli_reference_drift.py test_cli_reference_generated.py` -> `pass`
- `S03` `A` `src/vaultspec_core/tests/cli/test_cli_reference_surface.py`
- `S03` `verify:` `pytest test_cli_reference_surface.py` -> `pass`
