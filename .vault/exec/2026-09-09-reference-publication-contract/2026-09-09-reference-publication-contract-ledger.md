---
tags:
  - '#exec'
  - '#reference-publication-contract'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c52be9b5e0d4f87f9d63bcc237f0b176bbd77d81a7f18e31676e64310e9c90ca'
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
- `S04` `M` `src/vaultspec_core/cli/reference_gen.py`
- `S04` `verify:` `just check-type-strict` -> `pass`
- `S05` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S05` `M` `docs/CLI.md`
- `S05` `M` `.pre-commit-config.yaml`
- `S05` `M` `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`
- `S05` `verify:` `pytest test_cli_reference_generated.py` -> `pass`
- `S06` `A` `dev/guards/test_reference_attribution.py`
- `S06` `verify:` `pytest dev/guards/test_reference_attribution.py` -> `pass`

## Notes

- `S06` The new guard found a second hand-written caveat the issue did not list; it names a frozen schema boundary rather than availability, so the guard was narrowed to availability claims instead of rewording it.
