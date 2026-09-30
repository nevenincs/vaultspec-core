---
tags:
  - '#exec'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:178248771306fb7dd927d95b4684d114030da849c3dcd79752437be2d886ac8d'
related:
  - "[[2026-09-30-release-standard-plan]]"
---

# `release-standard` ledger

## Changes

- `S01` `A` `.vault/research/2026-09-30-release-standard-research.md`
- `S01` `A` `.vault/adr/2026-09-30-release-standard-adr.md`
- `S01` `M` `.vault/adr/2026-03-22-clci-release-adr.md`
- `S01` `M` `.vault/adr/2026-09-18-release-publication-ordering-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S02` `M` `.github/workflows/release-please.yml`
- `S02` `M` `release-please-config.json`
- `S02` `M` `.github/ci-contract-allow.txt`
- `S02` `M` `.github/workflows/merge-gate.yml`
- `S02` `verify:` `just check-workflow` -> `pass`
- `S02` `verify:` `shellcheck -s bash release-please.yml run blocks` -> `pass`
- `S03` `D` `.github/workflows/release.yml`
- `S03` `M` `.github/workflows/binaries.yml`
- `S03` `verify:` `just check-workflow` -> `pass`
- `S04` `M` `dev/guards/test_automation_contracts.py`
- `S04` `verify:` `pytest dev/guards` -> `pass`
- `S04` `verify:` `guard mutation proofs for the two rewritten release guards` -> `pass`
- `S05` `M` `docs/README.md`
- `S05` `verify:` `just check-markdown` -> `pass`
- `S05` `verify:` `just check-links` -> `pass`
- `S10` `M` `.github/workflows/merge-gate.yml`
- `S10` `verify:` `just check-workflow` -> `pass`
- `S10` `verify:` `shellcheck -s bash merge-gate.yml gate run blocks` -> `pass`
- `S11` `M` `dev/guards/test_ci_check_shape.py`
- `S11` `verify:` `pytest dev/guards` -> `pass`
- `S11` `verify:` `guard mutation proofs for the author clause and the untrusted refusal` -> `pass`
- `S12` `M` `.github/workflows/model-drift.yml`
- `S12` `verify:` `just check-workflow` -> `pass`
- `S13` `M` `.github/workflows/main-health.yml`
- `S13` `verify:` `just check-workflow` -> `pass`
- `S10` `M` `dev/guards/test_ci_check_shape.py`
- `S10` `verify:` `pytest dev/guards/test_ci_check_shape.py` -> `pass`
- `S10` `verify:` `guard mutation proofs for the author clause and the untrusted refusal` -> `pass`

## Notes

- `S02` S02, S03 and S04 share one commit: the cut, the retired relay and the rewritten guards only pass together
- `S10` S10 and S11 share one commit: the guard fails without the rule it pins
- `S10` the author clause is written as two equality comparisons rather than contains(fromJSON()), so every repository's guard evaluator can decide it
