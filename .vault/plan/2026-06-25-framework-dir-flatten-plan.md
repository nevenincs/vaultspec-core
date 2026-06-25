---
tags:
  - '#plan'
  - '#framework-dir-flatten'
date: '2026-06-25'
modified: '2026-06-25'
tier: L2
related:
  - '[[2026-06-25-framework-dir-flatten-adr]]'
  - '[[2026-06-25-framework-dir-flatten-research]]'
---

# `framework-dir-flatten` plan

Flatten the redundant `rules/` wrapper inside the `.vaultspec/` framework dir so the installed layout mirrors the flat source builtins, with an upgrade migration for existing installs.

## Description

This plan implements the `framework-dir-flatten` ADR. The installed framework dir
currently nests every builtin resource group under a redundant `rules/` parent
(`.vaultspec/rules/rules/`, `.vaultspec/rules/skills/`, and so on), while the source
builtins at `src/vaultspec_core/builtins/` are already flat. The work collapses the path
resolution so resources land directly under `.vaultspec/`, adapts every path consumer,
ships an upgrade migration that relocates existing nested installs, and sweeps the test
suite and docs to the flat layout. Grounding confirmed the fulcrum is `init_paths` in
`src/vaultspec_core/core/types.py`; the resource name resolver `_resolve_path` in
`src/vaultspec_core/core/resources.py` receives its base dir as an argument and so needs
no edit once the fulcrum changes. Phase two of the wider builtins refactor (vaultspec-rag
pipeline enrollment) is parked and out of scope here.

## Steps

### Phase `P01` - collapse live path resolution

A fresh install writes resources directly under the framework dir with no doubled rules level.

- [x] `P01.S01` - collapse the seven framework-relative resource directory joins in init_paths from a doubled rules level to a single level; `src/vaultspec_core/core/types.py`.
- [x] `P01.S02` - pass the framework dir instead of its rules subdir at the three seed_builtins call sites and reword the affected comments; `src/vaultspec_core/core/commands.py`.

### Phase `P02` - adapt path-consumer helpers

Snapshot, revert, hydration, integrity, and resolver code resolve resources at the flat root and never treat bookkeeping as resources.

- [x] `P02.S03` - drop the rules segment across the snapshot, revert, and modified-builtins helpers, exclude the snapshots and providers.json bookkeeping from snapshot globbing, and fix the module docstrings; `src/vaultspec_core/core/revert.py`.
- [x] `P02.S04` - drop the rules segment from the templates path resolution; `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `P02.S05` - drop the rules segment from the resource directory paths; `src/vaultspec_core/vaultcore/checks/rename_integrity.py`.
- [x] `P02.S06` - reword the warning strings and comments that name the nested rules layout; `src/vaultspec_core/core/resolver.py`.

### Phase `P03` - reword stale layout docstrings

Module docstrings and headers describe the flat layout instead of the nested rules path.

- [x] `P03.S07` - reword the seed, list, and check docstrings that name the nested rules layout; `src/vaultspec_core/builtins/__init__.py`.
- [x] `P03.S08` - reword the layout references in the rules module docstrings and comments; `src/vaultspec_core/core/rules.py`.
- [x] `P03.S09` - reword the layout references in the skills module docstrings; `src/vaultspec_core/core/skills.py`.
- [x] `P03.S10` - reword the layout reference in the system module docstring; `src/vaultspec_core/core/system.py`.
- [x] `P03.S11` - reword the layout references in the agents module docstrings and comments; `src/vaultspec_core/core/agents.py`.
- [x] `P03.S12` - reword the layout reference in the hooks module docstring; `src/vaultspec_core/core/hooks.py`.
- [x] `P03.S13` - reword the layout reference in the mcps module docstring; `src/vaultspec_core/core/mcps.py`.

### Phase `P04` - author the upgrade migration

Existing nested installs relocate to the flat layout on the next upgrade or vault command, idempotently.

- [x] `P04.S14` - author the migration that relocates each nested resource directory up to the framework root via a staged move, handles the inner rules collision, excludes the snapshots and providers.json bookkeeping, and stays idempotent; `src/vaultspec_core/migrations/m_0_1_35_framework_flatten.py`.
- [x] `P04.S15` - register the migration in the ordered registry and widen the vault-only mutation contract docstring to admit framework dir relocation; `src/vaultspec_core/migrations/__init__.py`.
- [x] `P04.S16` - author migration tests for idempotency, partial-failure re-run, and the inner rules collision using the workspace factory; `src/vaultspec_core/migrations/tests/test_framework_flatten.py`.

### Phase `P05` - sweep tests, fixtures, and docs

The suite and docs assert the flat layout and the full test run is green.

- [x] `P05.S17` - update the setup_rules_dir fixture and flat-layout directory creation in the cli conftest; `src/vaultspec_core/tests/cli/conftest.py`.
- [x] `P05.S18` - update the flat-layout directory creation in the protocol conftest; `src/vaultspec_core/protocol/tests/conftest.py`.
- [x] `P05.S19` - update the hardcoded paths and the rules-name assertion across the sync test cluster (collect, operations, manifest, incremental, parse); `src/vaultspec_core/tests/cli/ sync cluster`.
- [x] `P05.S20` - update the hardcoded paths in the install, live, collectors, ambiguous-states, manifest-migration-cluster, and rule-promote tests; `src/vaultspec_core/tests/cli/`.
- [x] `P05.S21` - update the snapshot, revert, and provider-hooks test paths; `src/vaultspec_core/core/tests/`.
- [x] `P05.S22` - update the templates path in the hydration and modified-stamp tests; `src/vaultspec_core/vaultcore/tests/`.
- [x] `P05.S23` - update the top-level mcp, commands, and template-annotation test paths; `tests/`.
- [x] `P05.S24` - reword the nested rules layout references; `docs/framework.md`.
- [x] `P05.S25` - reword the nested rules layout references; `docs/MCP.md`.

## Parallelization

Phases are sequenced. P01 (the path fulcrum) must land before P02 and P03, which adapt
the consumers and docstrings that depend on the new resolution. P04 (the migration)
depends on the final flat shape established by P01 and P02 so its relocation target
matches runtime expectations. P05 (the test and doc sweep) lands last because it asserts
the completed behaviour; within P05 the per-file Steps carry no interdependency and may
run in parallel.

## Verification

The plan is complete when every Step is closed and each of the following holds: a fresh
`vaultspec-core install` produces
`.vaultspec/{rules,skills,agents,system,templates,hooks,mcps,reference}/` with no
`.vaultspec/rules/rules/` path; the new migration relocates a synthesised nested install
to the flat layout and is a no-op on re-run; snapshot globbing never descends into
`_snapshots/`; and the full `pytest` run (not only the unit gate) is green with no
remaining hardcoded `.vaultspec/rules/<resource>` paths in source or tests.
