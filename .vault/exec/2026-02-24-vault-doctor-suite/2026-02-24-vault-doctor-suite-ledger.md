---
tags:
  - '#exec'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:af14c00952cdf515358b8c522cb40416178eef1a304b8a526b04a0ce97974d00'
related:
  - "[[2026-02-24-vault-doctor-suite-plan]]"
---

# `vault-doctor-suite` ledger

## Changes

- `S01` `A` `src/vaultspec_core/vaultcore/checks/_base.py`
- `S02` `A` `src/vaultspec_core/vaultcore/checks/__init__.py`
- `S03` `A` `src/vaultspec_core/cli/vault_check_cmd.py`
- `S04` `A` `src/vaultspec_core/vaultcore/checks/structure.py`
- `S05` `A` `src/vaultspec_core/vaultcore/checks/links.py`
- `S06` `A` `src/vaultspec_core/vaultcore/checks/orphans.py`
- `S07` `A` `src/vaultspec_core/vaultcore/checks/dangling.py`
- `S08` `A` `src/vaultspec_core/vaultcore/checks/references.py`
- `S09` `A` `src/vaultspec_core/vaultcore/checks/exec_mapping.py`
- `S10` `A` `src/vaultspec_core/vaultcore/checks/frontmatter.py`
- `S11` `A` `src/vaultspec_core/vaultcore/checks/markdown.py`
- `S12` `A` `src/vaultspec_core/vaultcore/checks/modified_stamp.py`
- `S13` `A` `src/vaultspec_core/vaultcore/checks/features.py`
- `S14` `A` `src/vaultspec_core/vaultcore/checks/tests/test_run_all.py`
- `S15` `A` `.pre-commit-config.yaml`
- `S16` `A` `src/vaultspec_core/mcp_server/tools/orientation.py`
- `S17` `M` `.vaultspec/reference/cli.md`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
