---
tags:
  - '#plan'
  - '#module-exports'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-02-21-module-exports-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:14b292962a2739851395375f1c2c5a60ea2ac9e545301d96267f86276404f2a0'
---

# `module-exports` plan

Establish a stable public API surface with `__all__` declarations and `__init__.py` re-exports across the package.

## Description

Reconstructed 2026-09-19 from this feature's historical execution records
(`2026-02-21-module-exports-p1-step07-exec`, `2026-02-21-module-exports-p1-step08-exec`),
which recorded completed work but had no surviving plan to attribute it to. The Steps
below restate what those records report as done; they are closed on that evidence, not
re-executed. Authorization is historical: the work shipped in February 2026 under the
`2026-02-21-module-exports-adr` decision to add `__all__` declarations, `__init__.py`
re-exports, and relative imports across the package.

Decision coverage: the `2026-02-21-module-exports-adr` (accepted) governs this work and
is linked in `related:`.

## Steps

- [x] `S01` - add __all__ and __init__.py re-exports for subagent_server and rewrite consumers to use package-level imports; `src/vaultspec/subagent_server/__init__.py`.
- [x] `S02` - retarget entry point imports and add __all__ to top-level modules and mcp_tools package; `src/vaultspec/mcp_tools/__init__.py`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report them, and
the work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: grep confirmed
no remaining deep imports for the re-exported symbols, and `python -m vaultspec --help`
and targeted `python -c` import checks passed at the time.
