---
tags:
  - '#plan'
  - '#packaging-restructure'
date: '2026-02-21'
modified: '2026-07-31'
body_hash: 'sha256:1fb1a82982a9509ba117f1b9e5e7d42aa72313f82bd047617a71b2921a1363d2'
tier: L2
related:
  - '[[2026-02-21-packaging-restructure-adr]]'
  - '[[2026-02-21-packaging-restructure-research]]'
---

# `packaging-restructure` `p1+p2` plan

### Phase `P01` - Package layout and file moves

Move library packages and CLI scripts into src/vaultspec, delete _paths.py, and relocate tests to the top level

- [x] `P01.S01` - create the src/vaultspec package directory structure; `src/vaultspec_core`.
- [x] `P01.S02` - move all library packages into the src/vaultspec namespace package; `src/vaultspec_core`.
- [x] `P01.S03` - move cli scripts into the package as proper modules and delete _paths.py; `src/vaultspec_core/cli`.
- [x] `P01.S04` - move test directories to the top level and adjust path derivation; `src/vaultspec_core/tests`.

### Phase `P02` - Import rewrite to namespaced form

Rewrite all bare-name imports across production code, servers, CLI modules, and tests to vaultspec-prefixed imports

- [x] `P02.S05` - rewrite bare-name imports in leaf packages to vaultspec-prefixed form; `src/vaultspec_core/vaultcore`.
- [x] `P02.S06` - rewrite bare-name imports in mid-tier packages to vaultspec-prefixed form; `src/vaultspec_core/protocol`.
- [x] `P02.S07` - rewrite bare-name imports in analytics packages to vaultspec-prefixed form; `src/vaultspec_core/graph`.
- [x] `P02.S08` - rewrite bare-name imports in server and cli modules and remove _paths references; `src/vaultspec_core/mcp_server`.
- [x] `P02.S09` - rewrite bare-name imports in all test and conftest files; `src/vaultspec_core/tests`.

### Phase `P03` - Packaging configuration

Switch the build backend to hatchling with uv, add project.scripts entry points, and point mcp.json at the packaged entry point

- [x] `P03.S10` - update pyproject.toml for hatchling and uv with project.scripts entry points; `pyproject.toml`.
- [x] `P03.S11` - add root package __init__.py and __main__.py; `src/vaultspec_core/__main__.py`.
- [x] `P03.S12` - remove the framework_root/lib validation check from workspace resolution; `src/vaultspec_core/config/workspace.py`.
- [x] `P03.S13` - update mcp.json to use the packaged vaultspec-mcp entry point; `.mcp.json`.

### Phase `P04` - Phase 1 verification

Verify the editable install, full test suite, CLI entry point, and MCP server all work after restructuring

- [ ] `P04.S14` - run uv sync --dev and confirm the editable install resolves; `pyproject.toml`.
- [ ] `P04.S15` - run the full test suite and confirm all tests pass; `src/vaultspec_core/tests`.
- [x] `P04.S16` - run the packaged CLI entry point and confirm it prints help; `src/vaultspec_core/__main__.py`.
- [x] `P04.S17` - smoke test the packaged MCP server entry point; `src/vaultspec_core/mcp_server/app.py`.

### Phase `P05` - Unified MCP server scaffolding

Scaffold a unified MCP server entry point that aggregates existing tools under a modular router pattern for future tool expansion

- [x] `P05.S18` - create the unified FastMCP server entry point; `src/vaultspec_core/mcp_server/app.py`.
- [x] `P05.S19` - refactor existing tool registrations into the unified server; `src/vaultspec_core/mcp_server/tools`.
- [x] `P05.S20` - add tool router modules for future phases; `src/vaultspec_core/mcp_server/tools`.
- [x] `P05.S21` - update all references from the legacy server name to vaultspec-mcp; `.mcp.json`.
- [x] `P05.S22` - verify the unified mcp server starts and registers all tools; `src/vaultspec_core/mcp_server/tests`.
