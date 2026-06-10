---
name: vaultspec-team
description: Skill to start coding teams for tackling difficult coding challenges.
---

# Team Coordination Skill (vaultspec-team)

This skill defines how to supervise multiple specialized agent personas when work is too
large for a single worker. Use it for massive refactors, multi-module auditing, or any
scenario where parallel execution and multi-agent coordination provide an advantage. The
work itself follows the plan-hardening convention: a Wave / Phase / Step plan governs
scope, and each Step is one prompt-run plus one commit.

**Announce at start:** "I'm using the `vaultspec-team` skill to coordinate a team of
agent personas."

## When to Use

- The work spans multiple modules, repositories, or domains.
- Parallel execution would significantly reduce total effort.
- The work benefits from specialized roles (researcher, coder, reviewer) working in
  coordination.

For focused, single-persona work, load the agent persona directly instead.

## Mechanism

This skill is a coordination policy, not a shipped MCP API contract.

- The host environment selects the participating agent personas.
- The host environment assigns Step / Phase / Wave boundaries, context, and sequencing
  per the plan document.
- The host environment monitors progress, handles permission prompts, and decides when
  to re-route or stop work.

Use this skill when you need a supervised team shape such as:

- researcher -> author -> editor
- researcher -> executor -> reviewer
- supervisor with multiple parallel specialists
