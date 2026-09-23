---
tags:
  - '#exec'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:eb06a4149612f18f89508e811e0abbe25cd2e909d6dd74c248bf9ffbfc1de546'
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
- `S04` `M` `src/vaultspec_core/core/prek_boundary.py`
- `S04` `M` `src/vaultspec_core/core/precommit.py`
- `S04` `M` `src/vaultspec_core/core/diagnosis/collectors_precommit.py`
- `S04` `M` `src/vaultspec_core/core/gitignore.py`
- `S04` `M` `src/vaultspec_core/core/uninstall.py`
- `S04` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S04` `A` `src/vaultspec_core/tests/cli/test_precommit_yml_config.py`
- `S04` `verify:` `ty check` -> `pass`

## Notes

- `S03` authorized by the user's direct request to fix just init; not governed by the proposed ADR
