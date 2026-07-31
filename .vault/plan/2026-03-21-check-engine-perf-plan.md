---
tags:
  - '#plan'
  - '#check-engine-perf'
date: '2026-03-21'
modified: '2026-07-31'
body_hash: 'sha256:14bdfe20915be268d9fa2a5a752911bd6a031f7d88b0d81a7d4a5a5c6fbd487c'
tier: L2
related:
  - '[[2026-03-21-check-engine-perf-adr]]'
  - '[[2026-03-21-check-engine-perf-research]]'
---

# check-engine-perf plan

### Phase `P01` - graph-consuming checkers

share one VaultGraph across the checkers that need it instead of each building its own

- [x] `P01.S01` - require a graph parameter on check_orphans, check_references, and check_schema and remove their internal graph construction; `src/vaultspec_core/vaultcore/checks/orphans.py`.

### Phase `P02` - snapshot-consuming checkers

derive one VaultSnapshot from the shared graph and pass it to the remaining checkers

- [x] `P02.S02` - define VaultSnapshot and derive it from a VaultGraph via to_snapshot; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S03` - require a snapshot parameter on check_structure, check_frontmatter, check_links, and check_features and remove their internal scans; `src/vaultspec_core/vaultcore/checks/frontmatter.py`.

### Phase `P03` - wire the shared graph and snapshot into run_all_checks and the standalone CLI

build the graph and snapshot once per invocation and reuse them everywhere

- [x] `P03.S04` - build a single graph and derived snapshot in run_all_checks and pass them to every checker; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P03.S05` - construct the graph and snapshot at each standalone CLI check call site before invoking the checker; `src/vaultspec_core/cli/vault_check_cmd.py`.
