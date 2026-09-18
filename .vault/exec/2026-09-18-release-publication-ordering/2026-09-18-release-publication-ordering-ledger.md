---
tags:
  - '#exec'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:e1f57328af09b8ff987108b01d691801c04425dc40763d4f1a666c4827998d00'
related:
  - "[[2026-09-18-release-publication-ordering-plan]]"
---

# `release-publication-ordering` ledger

## Changes

- `S01` `M` `release-please-config.json`
- `S01` `M` `dev/guards/test_automation_contracts.py`
- `S01` `verify:` `pytest dev/guards/test_automation_contracts.py` -> `pass`
- `S02` `M` `.github/workflows/binaries.yml`
- `S02` `M` `.github/workflows/publish.yml`
- `S02` `M` `.github/ci-contract-allow.txt`
- `S02` `M` `dev/guards/test_automation_contracts.py`
- `S02` `M` `dev/guards/test_release_matrix_coverage.py`
- `S02` `verify:` `pytest dev/guards -m repo` -> `pass`
- `S03` `M` `docs/README.md`
- `S03` `verify:` `pymarkdown scan` -> `pass`
- `S04` `M` `.github/ci-contract-allow.txt`

## Notes

- `S02` Scope widened to publish.yml: the distribution is attached there, so the release could not be published from the binaries lane, and the acquisition dispatch had to follow publication because it acquires unauthenticated.
- `S04` No tracked file: PUT /repos/nevenincs/vaultspec-core/immutable-releases returned 204 and the setting now reads enabled=true, enforced_by_owner=false. It was disabled earlier in the session to unblock an asset upload; the draft ordering is what makes it safe to hold.
- `S04` Correction: the S04 row naming .github/ci-contract-allow.txt is wrong. That file was touched by S02 and not by this Step, which changed no tracked file at all. The row is left in place because this ledger is append-only.
