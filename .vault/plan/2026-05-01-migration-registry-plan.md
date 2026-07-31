---
tags:
  - '#plan'
  - '#migration-registry'
date: '2026-05-01'
modified: '2026-07-31'
body_hash: 'sha256:e7a2936517cb242a044bf1a4691779b88539c87640a58b032e4449ba7f64b78c'
tier: L2
related:
  - '[[2026-05-01-migration-registry-adr]]'
  - '[[2026-05-01-migration-registry-research]]'
---

# `migration-registry` plan

## Steps

### Phase `P01` - implementation

Build a schema-migration registry and wire it into install, scan, doctor, and the CLI so no path performs ad hoc migration mutation.

- [x] `P01.S01` - lift parse_version_tuple into core/helpers.py for use without a circular import; `src/vaultspec_core/core/helpers.py`.
- [x] `P01.S02` - build the migration registry skeleton (Migration, MigrationResult, MigrationStatus, REGISTRY, run_pending_migrations); `src/vaultspec_core/migrations/__init__.py`.
- [x] `P01.S03` - add the first registry entry migrating legacy root-level indexes into the index subfolder; `src/vaultspec_core/migrations/m_0_1_17_index_subfolder.py`.
- [x] `P01.S04` - trigger pending migrations from install_run's upgrade branch; `src/vaultspec_core/core/provision.py`.
- [x] `P01.S05` - trigger pending migrations lazily from scan_vault with a per-process cache; `src/vaultspec_core/vaultcore/scanner.py`.
- [x] `P01.S06` - add a migrations status/run CLI subcommand mounted at the root level; `src/vaultspec_core/cli/migrations_cmd.py`.
- [x] `P01.S07` - integrate migration status into doctor diagnosis and exit-code semantics; `src/vaultspec_core/core/diagnosis/diagnosis.py`.
- [x] `P01.S08` - drop the mutating migration call from check_structure and replace it with non-mutating detection pointing at migrations run; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P01.S09` - update the pre-commit hook docstring to stop claiming schema migration; `.pre-commit-hooks.yaml`.
- [x] `P01.S10` - add registry-mechanics and trigger-site tests for the migration registry; `src/vaultspec_core/migrations/tests`.

### Phase `P02` - verification

Confirm quality gates, sweep for stale ad hoc migration references, and finalize the PR.

- [ ] `P02.S11` - confirm quality gates pass clean (doctor, vault check all, pytest, ty, ruff); `src/vaultspec_core`.
- [x] `P02.S12` - sweep for stale references to the removed ad hoc migration mutation; `src/vaultspec_core/vaultcore/checks`.
