---
tags:
  - '#plan'
  - '#module-exports'
date: '2026-02-21'
modified: '2026-07-31'
body_hash: 'sha256:a7e302205a3b8e6c0d9468d851af49cbd5c2787ab5873adc1e81e70266684fb3'
tier: L2
related:
  - '[[2026-02-21-module-exports-adr]]'
  - '[[2026-02-21-module-exports-part1-research]]'
  - '[[2026-02-21-module-exports-part2-research]]'
  - '[[2026-02-21-module-exports-part3-research]]'
---

# `module-exports` plan

### Phase `P01` - Leaf package exports

Add __all__ declarations and eager __init__.py re-exports for the config, vaultcore, and hooks packages, then rewrite consumers to package-level imports

- [x] `P01.S01` - add __all__ declarations and eager __init__.py re-exports for the config, vaultcore, and hooks packages; `src/vaultspec_core/vaultcore`.
- [x] `P01.S02` - rewrite consumers of config, vaultcore, and hooks to use package-level imports; `src/vaultspec_core`.

### Phase `P02` - Analytics package exports

Add __all__ and eager re-exports for the graph, metrics, and verification/diagnosis packages

- [x] `P02.S03` - add __all__ and eager __init__.py re-exports for the graph, metrics, and diagnosis packages; `src/vaultspec_core/graph`.

### Phase `P03` - RAG package lazy exports

Add __all__ and __getattr__-based lazy re-exports for the rag package and rewrite its consumers

- [ ] `P03.S04` - add __all__ and lazy __getattr__-based re-exports for the rag package and rewrite its consumers; `pyproject.toml`.

### Phase `P04` - Orchestration selective exports

Add __all__ and selective __init__.py re-exports for the orchestration package and rewrite its consumers

- [ ] `P04.S05` - add __all__ and selective __init__.py re-exports for the orchestration package and rewrite its consumers; `pyproject.toml`.

### Phase `P05` - Protocol hierarchy exports

Add __all__ and eager re-exports across the protocol provider hierarchy and rewrite consumers

- [x] `P05.S06` - add __all__ and eager re-exports across the protocol provider hierarchy and rewrite consumers; `src/vaultspec_core/protocol`.

### Phase `P06` - Subagent server exports

Add __all__ and eager re-exports for the subagent_server package and rewrite its consumers

- [ ] `P06.S07` - add __all__ and eager re-exports for the subagent_server package and rewrite its consumers; `src/vaultspec_core/mcp_server`.

### Phase `P07` - Entry points and test import migration

Retarget entry point and top-level module imports to package-level exports, then rewrite all test imports

- [x] `P07.S08` - retarget entry point imports and add __all__ to top-level modules; `src/vaultspec_core/cli`.
- [x] `P07.S09` - rewrite all test imports to use package-level imports; `src/vaultspec_core/tests`.

### Phase `P08` - Full verification pass

Run the full test suite and grep-based audits to confirm the module export refactor introduced zero regressions

- [ ] `P08.S10` - run the full verification pass: sync, full test suite, bare-import grep audit, and REPL smoke test; `pyproject.toml`.
