---
tags:
  - '#reference'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3162e30b234883d822061e6269c6b52df7f8fbe9cda67f6f1b3a1380ddec6214'
related:
  - "[[2026-06-05-plan-serializer-fixes-adr]]"
  - "[[2026-06-27-rename-convergence-adr]]"
---

# `plan-mutation-concurrency` reference: `plan mutation concurrency boundaries`

Code-grounded survey of plan mutation persistence and the repository's existing
concurrency primitives. The CLI and MCP plan surfaces, shared filesystem helpers,
document edit engine, and rename transaction engine were read on 2026-08-13 at
commit `02f92d3e`.

## Summary

### The current plan paths lock neither the read nor the write

Every CLI container verb reads and parses the plan before calling the common
`save_plan_or_dry_run`; representative phase and step paths are
`src/vaultspec_core/cli/plan_cmd_phase.py:54` and
`src/vaultspec_core/cli/plan_cmd_step.py:52`. The helper serialises, guards,
atomically replaces, re-reads, and verifies the result at
`src/vaultspec_core/cli/plan_cmd_shared.py:121`, but it receives an already-mutated
model and therefore cannot serialize the preceding read-modify interval.

The MCP surface repeats the boundary: `_load_plan` reads at
`src/vaultspec_core/mcp_server/tools/plan.py:185`; `plan_edit` loads before applying
its batch at `src/vaultspec_core/mcp_server/tools/plan.py:464`; `_save_plan` writes
at `src/vaultspec_core/mcp_server/tools/plan.py:200`. Two writers can consequently
parse the same revision, independently allocate or edit identifiers, and have the
later atomic replacement discard the earlier result. Post-write verification proves
only that each writer observed its own replacement before returning; it cannot prove
that no later writer replaced it.

### Existing primitives already encode the necessary critical section

`advisory_lock` explicitly serializes concurrent read-modify-write cycles across
threads and processes, including Windows, at
`src/vaultspec_core/core/helpers.py:84`. `atomic_write_bytes` provides crash-safe
replacement, not mutual exclusion, at `src/vaultspec_core/core/helpers.py:325`.
Both are required: the lock prevents lost updates while atomic replacement prevents
partial destination content.

The generic document edit engine derives ignored, per-document sentinels with
`document_lock_target` at `src/vaultspec_core/vaultcore/edit_engine.py:333`, creates
the sentinel parent for real writes, and holds the lock across current-byte guard,
composition, validation, write, and post-write hash at
`src/vaultspec_core/vaultcore/edit_engine.py:713`. This is the nearest same-file
read-modify-write analogue.

The rename engine separately defines one docs-domain sentinel at
`src/vaultspec_core/vaultcore/rename_engine.py:91` and a deterministic domain-then-
document acquisition order in `RenameTransaction` at
`src/vaultspec_core/vaultcore/rename_engine.py:153`. Batch archive re-runs preflight
inside that transaction at `src/vaultspec_core/vaultcore/batch_archive.py:152`.
Plan mutations change one existing document and do not need rename rollback or a
whole-domain freeze; their natural granularity is the existing per-document sentinel.

### A shared transaction owner avoids surface drift

Adding a lock only inside `save_plan_or_dry_run` is insufficient because all CLI
parsing and mutation already happened. Adding locks independently to every command
duplicates the critical-section contract across step, phase, wave, epic, tier, and
MCP paths. A plan-layer transaction helper should own sentinel materialisation and
the lock-scoped load-mutate-save sequence, while retaining the current CLI and MCP
presentation helpers. Dry runs may remain point-in-time previews and avoid creating
runtime state, matching the established archive preview contract.

### Test boundary

The decisive regression is real concurrent behavior: two independent callers mutate
one real plan and both changes survive. It must exercise production entry points and
filesystem locking without mocks, patches, monkeypatching, sleeps as synchronization,
or mirrored allocation logic. A process boundary is preferable on Windows because it
proves the OS lock rather than only the in-process thread lock. Existing focused tests
at `src/vaultspec_core/tests/plan/test_write_verification.py:48` cover write
verification but not serialization of competing read-modify-write cycles.
