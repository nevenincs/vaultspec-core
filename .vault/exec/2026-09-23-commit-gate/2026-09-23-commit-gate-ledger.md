---
tags:
  - '#exec'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:6d91898c51e2aea4a7199ae9a51ef78720f6b04246e5720387187d2361de43de'
related:
  - "[[2026-09-23-commit-gate-plan]]"
---

# `commit-gate` ledger

## Changes

- `S03` `M` `dev/init/plan.py`
- `S03` `A` `dev/tests/test_init_plan.py`
- `S03` `M` `justfile`
- `S03` `M` `dev/init/README.md`
- `S03` `M` `docs/framework.md`
- `S03` `verify:` `ty check` -> `pass`
- `S01` `M` `.vault/adr/2026-05-15-template-annotation-sanitization-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`

## Notes

- `S03` authorized by the user's direct request to fix just init; not governed by the proposed ADR
