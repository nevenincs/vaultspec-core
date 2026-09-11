---
name: vaultspec-team
description: Start a multi-agent coding team for a hard challenge. Use when a problem is too large for a single agent.
---

# Team coordination skill (vaultspec-team)

This skill defines how to supervise multiple specialized agent personas when work is too
large for a single worker. Use it for massive refactors, multi-module auditing, or any
scenario where parallel execution and multi-agent coordination provide an advantage. The
work itself follows the plan conventions: a Wave / Phase / Step plan governs scope, and
each Step is one prompt-run plus one commit.

**Announce at start:** "I'm using the `vaultspec-team` skill to coordinate a team of
agent personas."

## When to use

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

## Mapping the team to the plan

The plan document is the team's work queue; the plan's structure decides the team's
shape:

- Assign whole Phases (or Waves at L3/L4) to workers, never fragments of a Phase; the
  plan's Parallelization section states which containers may run concurrently.
- Each worker executes its Steps under the `vaultspec-execute` discipline: one Step is
  one prompt-run plus one commit, closed via `vaultspec-core vault plan step check`,
  with one Step Record per Step.
- Workers must not mutate plan structure; structural changes route back to the
  supervisor, who applies them via the `vaultspec-core vault plan` verbs.
- The supervisor enforces the mandatory review gate: a `vaultspec-code-reviewer` persona
  audits completed work before the affected Steps are reported done.

Use this skill when you need a supervised team shape such as:

- researcher -> author -> editor
- researcher -> executor -> reviewer
- supervisor with multiple parallel specialists
