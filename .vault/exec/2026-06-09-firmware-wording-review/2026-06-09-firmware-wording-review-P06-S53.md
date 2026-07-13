---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S53
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# name the vaultspec-researcher persona as the generic persona for multi-researcher coordination (D8)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`

## Description

- Extend the persona-loading paragraph: when the task benefits from multiple
  researchers, load the generic `vaultspec-researcher` agent persona for the
  additional research threads, coordinated through the host environment
- Keep `vaultspec-adr-researcher` as the focused single-researcher default and the
  hedged no-shipped-MCP-runtime wording from P01/P04 intact
- Adjust the instruction sentence to address each researcher
- Format with mdformat at wrap 88

## Outcome

The `vaultspec-researcher` persona, previously loaded by nothing (research finding:
orphaned firmware members), now has a documented loader: the research skill names it
as the generic persona for multi-researcher coordination while the adr-researcher
remains the focused default. Together with S52's reference-auditor wiring, every
shipped persona is now reachable from at least one skill.

## Notes

None.
