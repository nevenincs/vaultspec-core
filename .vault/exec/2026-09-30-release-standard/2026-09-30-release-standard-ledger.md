---
tags:
  - '#exec'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:50a56675b0544826f88c6bc468e90067ea513c76f3634c21f5c09a82f26768cb'
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

## Notes

- `S02` S02, S03 and S04 share one commit: the cut, the retired relay and the rewritten guards only pass together
