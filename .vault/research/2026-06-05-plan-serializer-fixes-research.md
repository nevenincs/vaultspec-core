---
tags:
  - '#research'
  - '#plan-serializer-fixes'
date: '2026-06-05'
modified: '2026-06-05'
related: []
---

# `plan-serializer-fixes` research: `serializer-and-obsolete-agents`

Research and investigation into two issues:

1. Issue 150: The serializer moving visible phases/steps into the retired ledger comment block during later unrelated mutations.
1. Issue 149: Pruning legacy `.codex/agents/` files and duplicate keys in `.codex/config.toml` that trigger loader warnings and TOML parse crashes.

## Findings

### 1. Issue 150 - Unexpected Retirements

- The CLI command handlers like `step remove` or `step add` perform localized mutations on a parsed plan, then serialize the plan back to disk.
- There is no logic that automatically retires visible phases or steps unless they are explicitly targeted by destructive commands like `step remove`, `phase remove`, `wave remove`, `renumber_phase`, or `demote_tier`.
- However, if the parser fails to parse or associate phases/steps with their waves (e.g. because of non-monotonicity or layout issues), they are not rendered in the visible body but are preserved. If a user manually recovers or edits, they may be retired.
- To prevent any silent retirement, we can add a check in `_save_plan_or_dry_run` that parses the original plan and compares the set of retired identifiers before and after the mutation. Any retirement not matching the target of the command (e.g. `remove_step` targets one step, `remove_phase` targets one phase and its steps) is rejected with a `PlanCommandError`.

### 2. Issue 149 - Legacy Codex Agents

- Legacy versions of `vaultspec-core` stored Codex agents in individual TOML files under `.codex/agents/`. The current system syncs them into a unified block in `.codex/config.toml` and configures `agents_dir` as `None` for Codex.
- Because `agents_dir` is `None`, the sync engine does not prune `.codex/agents/` when `prune=True`. This causes the config loader to warning about duplicate agent role names.
- In some environments, duplicates exist outside the managed comment block, e.g. as `[agents]` with sub-keys, causing standard TOML parser crashes with duplicate table keys.
- To fix this:
  - We will update `_sync_codex_agents` to check if `prune=True` is requested, and if so, prune `.codex/agents/` and remove the directory if empty.
  - We will update `_strip_agent_tables_in_segment` in `src/vaultspec_core/core/agents.py` to match and strip both `[agents.name]` tables and `name = ...` key assignments under `[agents]` tables that lie outside the managed tag blocks.
