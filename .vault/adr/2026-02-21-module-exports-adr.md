---
tags:
  - '#adr'
  - '#module-exports'
date: '2026-02-21'
modified: '2026-09-19'
body_hash: 'sha256:098df509a5bb3a4a99eb58aecb69432aee7e3e50202b20ad1f564a3063ed76a5'
related:
  - '[[2026-02-21-module-exports-part1-research]]'
  - '[[2026-02-21-module-exports-part2-research]]'
  - '[[2026-02-21-module-exports-part3-research]]'
  - '[[2026-02-21-packaging-restructure-adr]]'
---

# `module-exports` adr: `__all__ + __init__ re-exports + relative imports` | (**status:** `accepted`)

## Problem Statement

The package uses absolute imports everywhere (`from vaultspec_core.core.config import get_config`). There are no `__all__` declarations, no `__init__.py` re-exports, and consumers reach deep into sub-module internals. This couples every consumer to the internal file structure -- renaming a file or moving a function between modules within a package breaks all external callers. There is no stable public API surface.

## Considerations

The `2026-02-21-module-exports-part1-research`, `2026-02-21-module-exports-part2-research`, and `2026-02-21-module-exports-part3-research` documents provide an exhaustive audit of the current import structure. Key findings that inform this decision:

- **Scale**: approximately 160 absolute imports exist in production code and approximately 224 in test files, totaling roughly 384 import statements that must be addressed. The work is mechanical but large.
- **Dependency DAG**: the package dependency graph is acyclic and well-ordered. `core` is a true leaf (zero internal dependencies). `vaultcore` depends only on `core` (all deferred). From there the graph fans out: `graph` and `metrics` depend on `vaultcore`. Execution order must follow this DAG bottom-up.
- **Three distinct re-export strategies are needed** based on package characteristics:
  - **Eager re-export**: the `__init__.py` imports from sub-modules at package load time. Safe and appropriate for packages with no heavy optional dependencies and no circular risk from eager loading. This is the default and the strategy that survives today.
  - **Selective re-export**: the `__init__.py` eagerly re-exports only the modules that have stdlib-only dependencies, leaving modules with heavy third-party dependencies as deep-import-only.
  - **Lazy re-export**: the `__init__.py` uses a `__getattr__`-based lazy loading pattern so that importing the package does not trigger import of heavy inference dependencies.
- **Entry points are excluded**: top-level entry-point modules are not consumed by other packages. They should keep absolute imports but target package-level exports once those exist (e.g., `from vaultspec_core.core import get_config` rather than `from vaultspec_core.core.config import get_config`).

## Constraints

- All approximately 384 import statements must be rewritten across production and test code.
- Tests should use public API imports (`from vaultspec_core.core import get_config`) to validate the API surface, except when explicitly testing private internals.
- `__all__` must be maintained going forward -- any new public symbol must be added to the relevant `__all__` list. This is a permanent maintenance obligation.
- A package whose `__init__.py` would otherwise pull in heavy optional dependencies must not do so eagerly.

## Implementation

Implementation proceeds in phases, ordered by the dependency DAG so that each phase can be verified independently before the next begins. Each phase follows the same mechanical pattern: add `__all__` to every module, populate `__init__.py` with re-exports, convert intra-package imports to relative form, and rewrite all consumers to use package-level imports.

Identifier note, amended 2026-09-19: this record was authored against the package name `vaultspec`. The import package is `vaultspec_core`. The identifiers below have been corrected; the decision -- `__all__`, `__init__.py` re-exports, relative intra-package imports -- is unchanged and in force across the tree.

### Phase 1: Leaf packages -- `core/`, `vaultcore/`, `hooks/`

`core` is consumed by every other package in the codebase. Stabilizing its API first maximizes downstream impact. `vaultcore` and `hooks` depend only on `core` (all deferred), making them safe to process in the same phase.

- Add `__all__` to every module in `core/`, `vaultcore/`, and `hooks/` using the declarations from `2026-02-21-module-exports-part1-research` and `2026-02-21-module-exports-part2-research`.
- Populate each package's `__init__.py` with eager re-exports from sub-modules using relative imports. For `core/__init__.py`: re-export the config and workspace API. For `vaultcore/__init__.py`: re-export its public symbols across its modules. For `hooks/__init__.py`: re-export `SUPPORTED_EVENTS`, `Hook`, `HookAction`, `HookResult`, `load_hooks`, `trigger`.
- Convert all intra-package imports to relative form (e.g., `from .models import DocType` within `vaultcore/scanner.py`).
- Rewrite all consumers of these three packages across the entire codebase to use package-level imports (e.g., `from vaultspec_core.core import get_config` instead of `from vaultspec_core.core.config import get_config`).

### Phase 2: Mid-tier analytics -- `graph/`, `metrics/`

These are single-module packages that depend on `vaultcore` (now package-level importable from Phase 1). They follow the same eager re-export pattern.

- Add `__all__` to each package's `api.py` using the declarations from `2026-02-21-module-exports-part3-research`.
- Populate each `__init__.py` with eager re-exports: `graph` re-exports `DocNode` and `VaultGraph`; `metrics` re-exports `VaultSummary` and `get_vault_metrics`.
- Rewrite consumers to use package-level imports (e.g., `from vaultspec_core.graph import VaultGraph`).

### Phase 3: `protocol/`

- Add `__all__` to every module using the declarations from `2026-02-21-module-exports-part2-research`.
- `protocol/providers/__init__.py` already has re-exports (the only existing example in the codebase). Extend it to cover the provider implementations and the full `base.py` public API.
- Convert all intra-package imports to relative form throughout the hierarchy.
- Rewrite consumers to use the appropriate package-level import (e.g., `from vaultspec_core.protocol.providers import ClaudeProvider`).

### Phase 4: Top-level entry points and tests

- Entry-point modules keep absolute imports but retarget them to package-level exports (e.g., `from vaultspec_core.core import get_config`). These are entry points, not library code -- relative imports provide no benefit here.
- `logging_config.py`: add `__all__` exporting `configure_logging` and `reset_logging`.
- Rewrite all test imports (approximately 224 statements) to use package-level imports where they target public API symbols. Tests that explicitly test private internals retain their deep imports.

### Phases for packages no longer in the tree (historical)

The original record also sequenced phases for `rag/` (lazy `__getattr__` re-export), `orchestration/` (selective re-export around SDK dependencies), `protocol/acp/` and `protocol/a2a/` including the executors hierarchy, `subagent_server/`, `verification/`, and the `mcp_tools/` stubs. None of those packages are in the tree. Semantic search is a separately distributed package, and the subagent, team, and A2A dispatch surface was removed. Those phases are retained here as the original sequencing intent; they are not pending work. The selective and lazy strategies they justified have no current subject, leaving eager re-export as the only strategy in force.

## Rationale

- `2026-02-21-module-exports-part1-research` established that `core` is the true leaf dependency consumed by every other package. Stabilizing it first ensures all subsequent phases can immediately use the new package-level imports, reducing the total number of intermediate states.
- `2026-02-21-module-exports-part2-research` identified the `protocol` package as the deepest hierarchy but confirmed that the `__init__.py` re-export pattern scales cleanly across nested sub-packages.
- `2026-02-21-module-exports-part3-research` quantified the total scope (approximately 384 imports), confirmed no circular risks exist with selective re-exports, and validated that leaf-first execution is the safest ordering.
- The `__all__` + `__init__.py` re-export pattern is standard Python practice. Major libraries (numpy, requests, FastAPI, pydantic) all use this approach to decouple their public API from their internal file structure.
- Relative imports within packages prevent the package from knowing its own absolute name, which supports future renaming or relocation without touching every internal import statement. This directly addresses the coupling problem identified in the problem statement, and it is what made the later rename of the distribution cheap.
- The three-strategy approach (eager, selective, lazy) was driven by concrete technical constraints rather than preference.

## Consequences

**Positive outcomes**:

- A stable public API surface emerges for every package. Internal file reorganization within a package no longer breaks external consumers as long as the `__init__.py` re-exports are maintained.
- `__all__` enforces intentional API design. Every public symbol is explicitly declared, making it clear what is part of the contract and what is an implementation detail.
- Consumer import statements become shorter and more uniform (`from vaultspec_core.core import get_config` rather than `from vaultspec_core.core.config import get_config`).
- Relative imports make packages self-contained and relocatable within the source tree.
- Tests that import from the public API surface serve as regression guards -- if a re-export is accidentally removed, the test suite catches it immediately.

**Negative outcomes**:

- Approximately 384 import statements must be rewritten. While mechanical, this is a large changeset that touches nearly every file in the codebase.
- `__all__` imposes a permanent maintenance burden. Every new public symbol must be added to the relevant `__all__` list, and the corresponding `__init__.py` re-export must be updated.
- Developers joining the project must learn the "import from the package, not the module" convention. Linting or code review enforcement may be needed to maintain discipline.

**Amendment note, 2026-09-19**: the namespace above was corrected from `vaultspec` to `vaultspec_core`, and the phases covering packages that are no longer in the tree were collected into one historical section rather than left reading as outstanding work. The decision is in force: `__all__` appears in 196 modules, `core/__init__.py` alone carries 82 re-export lines, and intra-package imports are relative throughout. No part of this decision was reversed, so this is an amendment rather than a supersession. The package rename and the extraction of semantic search into its own distribution are not recorded by any ADR in this corpus and still warrant one.
