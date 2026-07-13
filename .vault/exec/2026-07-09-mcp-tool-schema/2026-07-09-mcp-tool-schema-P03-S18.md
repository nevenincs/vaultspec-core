---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S18'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory tests for plan_progress, plan_edit, and the resolver: checked/unchecked batch marking, step add/insert/edit/remove identifier preservation, and the ambiguous-feature resolution error (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_plan_tools.py`

## Description

- Add the plan-tools test module over the same WorkspaceFactory-and-real-server harness, with no mocks, stubs, or skips.
- Cover `plan_edit`: add allocates S01 and S02, insert before S01 allocates the next id S03 (never reusing), edit updates S02, remove retires S01, and a subsequent add allocates S04 (proving gap-no-reuse); a failed op does not abort the batch; an empty batch is a protocol error.
- Cover `plan_progress`: checking a step advances completion and reports the next open step, re-checking is an idempotent unchanged no-op, unchecking re-opens; an unknown step id fails per item; an unresolvable plan is a protocol error.
- Cover the resolver directly: a feature owning two plans raises with two candidates while a unique stem still resolves, and an unknown target raises with no candidates.

## Outcome

- Coverage of plan_progress, plan_edit, and the shared resolver, including canonical-identifier preservation and the ambiguous-feature error, all green.

## Notes

- No blockers.
