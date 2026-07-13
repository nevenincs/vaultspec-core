---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S18'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Run vaultspec-core sync to propagate the reworded builtins into this repo's .claude provider directories and read the sync result for created/updated/unchanged status with no failures

## Scope

- `.claude/rules/vaultspec-cli.builtin.md`

## Description

- Run `install --upgrade` to refresh the dev firmware from the reworded sources; report `45 unchanged`, no failures.
- Run `vaultspec-core sync` to propagate the reworded builtins into every provider directory.
- Read the sync result: `81 unchanged` across claude, gemini, antigravity, and codex, no `failed` entries.

## Outcome

Full propagation succeeded with no failures. The synced provider copies were already consistent with the reworded builtins because the P01 through P03 and P04 commits carried their synced outputs alongside their sources, so this closeout sync is a clean no-op confirming consistency rather than a fresh copy. Working tree stays clean.

## Notes

The sync reporting all `unchanged` rather than `updated` is expected and correct here: `unchanged` is a successful no-op, and it proves the committed provider directories already match the reworded sources.
