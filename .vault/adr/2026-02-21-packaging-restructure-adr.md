---
tags:
  - '#adr'
  - '#packaging-restructure'
date: '2026-02-21'
modified: '2026-09-19'
body_hash: 'sha256:77d650170767c7b14fc114372ba16fa3e49f3493525cc1044bf194dad7695aae'
related:
  - '[[2026-02-21-packaging-restructure-research]]'
---

# `packaging-restructure` adr: `src layout + uv + unified MCP` | (**status:** `accepted`)

## Problem Statement

The Python codebase lives under `.vaultspec/lib/` -- a dotfile directory. Bare top-level package names (`core`, `orchestration`, `protocol`, `rag`, `vaultcore`, etc.) collide in site-packages with any other project that happens to ship a `core` or `protocol` package. All four CLI scripts bootstrap through `_paths.py`, which performs `sys.path.insert(0, ...)` surgery to make these bare imports work. No proper `[project.scripts]` entry points exist -- the MCP server is launched via raw script path in `mcp.json`. `python -m` execution does not work. The project cannot be cleanly installed, deployed, or consumed as a library.

## Considerations

- **`uv` as package manager**: Fast dependency resolution, PEP 621 native, first-class editable installs via `uv sync --dev`. The current `pyproject.toml` already uses PEP 621 metadata (`[project]` table, `[project.optional-dependencies]`), so adoption is low-friction.
- **src layout**: The Python community consensus for installable packages. Prevents import shadowing (the running directory cannot accidentally shadow the installed package). All 11 bare-name packages become submodules of one distribution package.
- **Single unified MCP server**: Replace the current `vs-subagent-mcp` (5 tools only) with `vaultspec-mcp` that aggregates the tool surface behind a modular router pattern. This consolidates the MCP surface into one process with one lifespan.
- **`hatchling` vs `setuptools`**: Both work with `uv`. `hatchling` is `uv`'s default and the more idiomatic choice for modern PEP 621 projects. `setuptools` is already configured but requires the `[tool.setuptools.packages.find]` indirection. Decision: switch to `hatchling` for cleaner `[tool.hatch.build.targets.wheel]` configuration.
- **Phased rollout**: The research identified ~149 import rewrites, 66 test files, and significant MCP tool expansion. A phased approach contains risk by separating the mechanical packaging work (Phase 1) from the MCP tool expansion (Phases 2-5).

## Constraints

- **149 bare-name imports** across production code (38), test code (78), scripts (21), and conftest files (12) must be rewritten mechanically to package-prefixed forms.
- **66 test files** are affected by the namespace change.
- **`.vaultspec/` must remain** as the framework configuration directory (rules, templates, agents, skills). It does not move -- only the Python source code under `.vaultspec/lib/src/` relocates into the src tree.
- **`core/workspace.py`** contains a `_validate()` check that asserts `framework_root/lib/` exists as a directory. After restructuring, Python code no longer lives there, so this validation must be updated or removed.
- **MCP tool expansion** and **RAG GPU/long-running patterns** are explicitly OUT OF SCOPE for this ADR. They are deferred to future phases to avoid conflating packaging concerns with API design concerns.

## Implementation

Implementation proceeds in phases. This ADR's core scope is **Phase 1** (package layout + `uv`) and **Phase 2** (unified MCP scaffolding). Phases 3-5 are scoped here for sequencing clarity but deferred to future ADRs for detailed design.

Identifier note, amended 2026-09-19: this record was authored against the name `vaultspec` and the path `src/vaultspec/`. The distribution is named `vaultspec-core` and the import package is `vaultspec_core`, under `src/vaultspec_core/`. The identifiers below have been corrected to the names the code actually carries so the record maps onto the tree; the decision itself -- src layout, `uv`, `hatchling`, real entry points, one unified MCP server -- is unchanged and in force. See the amendment note at the end of Consequences for what else diverged.

### Phase 1: Package layout + `uv`

This phase is entirely mechanical. The research in `2026-02-21-packaging-restructure-research` confirmed no circular dependencies in the import graph and that `vaultcore` is the most-depended-on leaf package -- a safe foundation to migrate first.

- Move `.vaultspec/lib/src/*` into the src tree. All packages become submodules of the import package: `vaultspec_core.core`, `vaultspec_core.protocol`, `vaultspec_core.vaultcore`, `vaultspec_core.graph`, `vaultspec_core.metrics`, `vaultspec_core.hooks`. The standalone `logging_config.py` becomes `vaultspec_core.logging_config`.
- Move `.vaultspec/lib/scripts/` entry points into the package as proper modules.
- Rewrite all 149 bare-name imports to the package namespace. This is a mechanical find-and-replace: `from core.workspace import ...` becomes `from vaultspec_core.core.workspace import ...`, etc.
- Delete `_paths.py` entirely. Workspace resolution already lives in the package; scripts no longer need bootstrap path surgery.
- Update `core/workspace.py` `_validate()` to remove the `framework_root/lib/` existence check. The `framework_root` continues to point at `.vaultspec/` for config resolution, but it no longer contains Python source.
- Update `pyproject.toml`:
  - Build backend: switch from `setuptools` to `hatchling`.
  - Package discovery: `[tool.hatch.build.targets.wheel] packages = ["src/vaultspec_core"]`.
  - Entry points: add `[project.scripts]`.
  - Test config: replace the `pythonpath` hack with standard installed-package imports.
- Add a `__main__.py` to enable `python -m vaultspec_core`.
- Add `[project.scripts]` entry points:
  - `vaultspec-core = "vaultspec_core.__main__:main"`
  - `vaultspec-mcp = "vaultspec_core.mcp_server.app:run"`
- Update `.mcp.json` to launch the server through its entry point instead of a raw script path.
- Update the `conftest.py` files and test constants to use namespaced imports.
- Verify `uv sync --dev` produces a working editable install where the package resolves correctly.

### Phase 2: Unified MCP server scaffolding

- Create the unified `vaultspec-mcp` entry point. This module instantiates a single server instance and aggregates tool routers.
- Migrate the existing subagent tools and dynamic agent resources into the unified server.
- Establish a modular tool registration pattern so that future phases can add tool modules without modifying the server core.
- Rename the MCP server from `vs-subagent-mcp` to `vaultspec-mcp` in all configuration.

### Phases 3-5 (superseded)

The phased MCP tool expansion scoped here -- vault and framework tools, team tools, and RAG tools as MCP tools -- was not built as described. The MCP surface is governed by `2026-07-09-mcp-tool-schema-adr`, and semantic search is owned by a separate distribution rather than by an in-tree `rag` package. These phases are recorded as original sequencing intent, not as pending work.

## Rationale

The research findings in `2026-02-21-packaging-restructure-research` provide strong evidence that this migration is safe and mechanical:

- **No circular dependencies** -- the import graph is a clean DAG with `vaultcore` at the bottom and `core` as a leaf. Migration order is unambiguous.
- **All CLI scripts are production-grade** -- no stubs, no dead code, no throwaway prototypes. Every script handler maps to a real feature. Nothing needs to be discarded.
- **No legacy packaging artifacts** -- no `requirements.txt`, `setup.cfg`, or `setup.py` exist. The starting point is clean PEP 621 metadata.
- **Standard src layout is community consensus** -- the `src/` directory layout prevents the common pitfall where running tests against the source tree accidentally imports the local directory instead of the installed package.
- **`uv` is the modern standard** -- PEP 621 native, fast resolution, first-class editable installs.
- **`_paths.py` is the single point of fragility** -- eliminating it in favor of proper package installation removes a class of "works on my machine" bugs entirely.

## Consequences

**Positive**:

- `python -m vaultspec_core` works out of the box.
- The MCP server launches through an entry point rather than a raw script path.
- No `sys.path` hacks anywhere -- `_paths.py` is deleted entirely.
- A proper package namespace prevents site-packages collisions.
- The project becomes cleanly installable.
- `.vaultspec/` becomes a pure configuration directory -- cleaner separation of concerns.
- Entry points (`[project.scripts]`) are the standard mechanism for console scripts.

**Negative**:

- 149 import rewrites are mechanical but tedious and touch nearly every file. A single missed rewrite causes an `ImportError` at runtime.
- All developers must switch to `uv sync --dev` for local development. The `sys.path` hack no longer works as a fallback.
- `.vaultspec/lib/` loses its scripts directory and becomes config-only. Any tooling or documentation referencing `.vaultspec/lib/scripts/` must be updated.
- The `hatchling` build backend is a new dependency in the build chain, though it is well-maintained and widely adopted.

**Amendment note, 2026-09-19**: three things this record described did not survive, and the text above has been corrected so it maps onto the tree rather than onto the names of the day.

- The distribution is `vaultspec-core` and the import package is `vaultspec_core`, not `vaultspec`. The src-layout decision is unchanged; only the name differs.
- Two console scripts exist, `vaultspec-core` and `vaultspec-mcp`, not the five originally listed. The three CLI-splitting entry points were never shipped as separate scripts; that surface is one CLI with subcommand groups.
- The `rag`, `orchestration`, `subagent_server`, and `verification` packages named in Phase 1, and the `protocol/acp` and `protocol/a2a` subpackages, are not in the tree. Semantic search moved to a separately distributed package; the subagent and team dispatch surface was removed from this package.

No decision recorded here was reversed by those changes, so this is an amendment rather than a supersession. The package identity itself -- the rename and the extraction of semantic search into its own distribution -- is not recorded by any ADR in this corpus and still warrants one.
