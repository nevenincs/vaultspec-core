---
tags:
  - '#plan'
  - '#mcp-consolidation'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:19e5c410dcdfe8384d23dc77396f3fc2d16ab7f498b32ed29ec4118024dec681'
tier: L2
related:
  - '[[2026-02-22-mcp-consolidation-adr]]'
  - '[[2026-02-22-mcp-consolidation-research]]'
  - '[[2026-02-21-packaging-restructure-adr]]'
  - '[[2026-02-22-cli-ecosystem-factoring-adr]]'
---

# `mcp-consolidation` plan

### Phase `P01` - Scaffold and move source files

Create the mcp_server package and move server.py, subagent_server, and mcp_tools content into it

- [x] `P01.S01` - create the mcp_server package and move the subagent, team, vault, and framework tool modules into it; `src/vaultspec_core/mcp_server`.
- [x] `P01.S02` - move the unified server entry point into mcp_server and update its internal imports; `src/vaultspec_core/mcp_server/app.py`.
- [x] `P01.S03` - write the mcp_server package init with the public re-exports; `src/vaultspec_core/mcp_server/__init__.py`.

### Phase `P02` - Move test files

Move the subagent_server and mcp_tools test suites into mcp_server/tests and update their relative imports

- [x] `P02.S04` - move the subagent_server and mcp_tools test suites into mcp_server tests and update relative imports; `src/vaultspec_core/mcp_server/tests`.

### Phase `P03` - Update external references

Retarget every external reference to the old server and mcp_tools module paths at the new mcp_server location

- [ ] `P03.S05` - update the package entry point and __main__ to reference mcp_server.app; `src/vaultspec_core/__main__.py`.
- [x] `P03.S06` - update pyproject.toml's vaultspec-mcp entry point to mcp_server.app; `pyproject.toml`.

### Phase `P04` - Delete old packages

Delete the superseded server.py, subagent_server, and mcp_tools modules once all references are retargeted

- [x] `P04.S07` - delete the standalone server.py, subagent_server, and mcp_tools packages; `src/vaultspec_core`.

### Phase `P05` - Verify

Confirm the mcp_server test suites pass and the consolidated import paths resolve

- [ ] `P05.S08` - run the mcp_server test suites and confirm they pass; `src/vaultspec_core/mcp_server/tests`.
- [x] `P05.S09` - confirm the mcp_server public entry points import correctly; `src/vaultspec_core/mcp_server/__init__.py`.
