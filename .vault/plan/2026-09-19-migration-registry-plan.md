---
tags:
  - '#plan'
  - '#migration-registry'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-05-01-migration-registry-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:d608ee5a579ae76da594f86e8f26133dd5e20dc8e6f0f14818dd9facfe9851f3'
---

# `migration-registry` plan

Add a version-gated migration registry that drives the index-subfolder move instead of the structure checker's ad hoc relocation.

## Description

Reconstructed 2026-09-19 from this feature's historical execution record
(`2026-05-01-migration-registry-phase1-summary-exec`), which recorded
completed Phase-1 work but had no surviving plan to attribute it to. The
Steps below restate the tasks that record reports shipped in commit
`fdc0609`; they are closed on its evidence, not re-executed. Authorization
is historical: the work shipped fixing GitHub issue #95.

Decision coverage: `[[2026-05-01-migration-registry-adr]]` governs the
registry mechanics, the driver's no-downgrade guarantee, and the trigger
sites this plan sequences.

## Steps

- [x] `S01` - lift parse_version_tuple from the resolver into a shared helper; `src/vaultspec_core/core/helpers.py`.
- [x] `S02` - add the migration registry skeleton with the status, run, and cache-reset helpers; `src/vaultspec_core/migrations/__init__.py`.
- [x] `S03` - add the first migration entry porting the index-subfolder relocation; `src/vaultspec_core/migrations/m_0_1_17_index_subfolder.py`.
- [x] `S04` - trigger pending migrations from install, scan_vault, and the doctor diagnosis; `src/vaultspec_core/core/provision.py`.
- [x] `S05` - add the migrations status and run CLI commands; `src/vaultspec_core/cli/migrations_cmd.py`.
- [x] `S06` - drop the legacy migration callsites from the structure checker; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `S07` - drop the schema-migration claim from the pre-commit hook docstring and document the new commands; `.pre-commit-hooks.yaml`.

## Parallelization

None. The tasks landed together in one Phase-1 implementation commit after
a rebase onto `main`, and the work is complete, so no container is
available for concurrent assignment.

## Verification

Verified historically by the execution record this plan reconstructs:
`ruff check`, `ruff format --check`, `ty check`, a 1383-test `pytest` run,
`vaultspec-core vault check all`, and `vaultspec-core spec doctor` all
reported clean, with 44 new tests covering registry mechanics, the
index_subfolder entry, and the three trigger sites.
