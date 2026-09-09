---
tags:
  - '#exec'
  - '#reference-publication-contract'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4fbb937b581d548d4096dafb56b3ae1ecea63d3e0a4ef4ee281c1803612ed77d'
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
- `S07` `M` `src/vaultspec_core/cli/reference_gen.py`
- `S07` `M` `src/vaultspec_core/cli/reference_surface.py`
- `S07` `verify:` `just check-type-strict` -> `pass`
- `S08` `M` `docs/MCP.md`
- `S08` `verify:` `vaultspec-core spec reference generate --check` -> `pass`
- `S09` `M` `src/vaultspec_core/tests/cli/test_cli_reference_surface.py`
- `S09` `M` `dev/guards/test_reference_attribution.py`
- `S09` `verify:` `pytest test_cli_reference_surface.py` -> `pass`
- `S10` `M` `.github/workflows/release-please.yml`
- `S10` `M` `justfile`
- `S10` `M` `dev/toolchain.py`
- `S10` `verify:` `just check-workflow` -> `pass`
- `S11` `M` `.github/workflows/publish.yml`
- `S11` `M` `justfile`
- `S11` `M` `src/vaultspec_core/cli/spec_cmd_reference.py`
- `S11` `verify:` `just release-verify-surface dist` -> `pass`
- `S12` `M` `dev/guards/test_reference_attribution.py`
- `S12` `M` `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`
- `S12` `verify:` `pytest dev/guards/test_reference_attribution.py` -> `pass`

## Notes

- `S06` The new guard found a second hand-written caveat the issue did not list; it names a frozen schema boundary rather than availability, so the guard was narrowed to availability claims instead of rewording it.
- `S11` Verified against a real wheel built from this tree: the recipe correctly reports a mismatch, because a wheel built from main declares the released version while carrying a larger surface. The failure now explains that state rather than reading as a defect.
- `S12` Each release-lane guard was proved able to fail: removing the refresh and the verification steps turns three of them red, and restoring the steps turns them green again.
