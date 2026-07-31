---
tags:
  - '#plan'
  - '#cli-ecosystem-factoring'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:95577ec541afc39c1c6c5acf72f035f2ed99e41464b9af4f6a09b110e62cf3dc'
tier: L2
related:
  - '[[2026-02-22-cli-ecosystem-factoring-adr]]'
  - '[[2026-02-22-cli-ecosystem-factoring-research]]'
---

# cli-ecosystem-factoring plan

## Steps

### Phase `P01` - Rename core to config

Free the vaultspec.core namespace for the domain library by renaming the configuration package to vaultspec.config

- [x] `P01.S01` - rename the configuration package and its tests from core to config; `src/vaultspec_core/config`.
- [x] `P01.S02` - update all consuming imports from vaultspec.core to vaultspec.config; `src/vaultspec_core`.

### Phase `P02` - Extract shared CLI foundation

Eliminate boilerplate duplication across CLI entry points by extracting shared version, argument, logging, workspace, and async helpers into cli_common

- [x] `P02.S03` - create cli_common with the shared version, argument, logging, workspace, and async-run helpers; `src/vaultspec_core/cli_common.py`.
- [x] `P02.S04` - refactor all cli entry points to use cli_common instead of duplicated boilerplate; `src/vaultspec_core/cli`.

### Phase `P03` - Extract business logic into a core domain library

Move resource management business logic out of the CLI layer into an independently importable and testable core domain library, then slim the CLI entry point to a thin dispatch wrapper

- [x] `P03.S05` - create the core domain library modules for types, helpers, sync, rules, agents, skills, config generation, system, and resources; `src/vaultspec_core/core`.
- [x] `P03.S06` - slim the cli entry point down to a thin dispatch wrapper over the core domain library; `src/vaultspec_core/cli`.

### Phase `P04` - Delete import-fallback antipatterns

Remove dead fallback code and silent degradation paths in the core domain library that mask installation errors

- [x] `P04.S07` - delete fallback import patterns and silent degradation paths in the core domain library; `src/vaultspec_core/core`.
