---
tags:
  - '#plan'
  - '#plan-serializer-fixes'
date: '2026-06-05'
modified: '2026-06-05'
tier: L2
related:
  - '[[2026-06-05-plan-serializer-fixes-adr]]'
  - '[[2026-06-05-plan-serializer-fixes-research]]'
---

# `plan-serializer-fixes` `serializer validation and obsolete codex agents pruning` plan

## Phases

### Phase `P01` - serializer validation

Ensure no unexpected active plan items are silently retired during mutations.

- [x] `P01.S01` - implement validation check in \_save_plan_or_dry_run; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `P01.S02` - update command handlers to compute and pass expected_retired; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `P01.S03` - write unit/regression tests for unexpected retirement check; `tests/cli/test_plan_cmd.py`.

### Phase `P02` - obsolete agents pruning

Clean up legacy agents directory and strip unmanaged config duplicates.

- [x] `P02.S04` - implement directory/file cleanup in \_sync_codex_agents; `src/vaultspec_core/core/agents.py`.
- [x] `P02.S05` - implement unmanaged duplicate agents tables and key stripping in \_strip_agent_tables_in_segment; `src/vaultspec_core/core/agents.py`.
- [x] `P02.S06` - write unit/integration tests for agents pruning and config stripping; `tests/core/test_agents.py`.

## Description

This plan addresses two main issues:

1. Issue 150: Verification that plan serialization mutations do not retire any unexpected elements.
1. Issue 149: Pruning legacy `.codex/agents/` directories and sanitizing unmanaged configurations to avoid duplicate agent definition errors.

## Parallelization

All steps are ordered linearly due to verification dependencies.

## Verification

Mission success criteria:

- Unexpected retirement checks raise `PlanCommandError` and prevent file write.
- Sync command successfully prunes obsolete `.codex/agents/` and strips duplicate unmanaged keys in `.codex/config.toml`.
- All tests pass.
