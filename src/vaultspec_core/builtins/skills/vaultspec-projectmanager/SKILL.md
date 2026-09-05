---
name: vaultspec-projectmanager
description: 'Coordinate GitHub Projects: triage issues, track milestones, provision worktrees, manage releases. Use for project management outside the pipeline.'
---

# Project manager skill (vaultspec-projectmanager)

Handles project-level coordination outside the vaultspec pipeline. This skill manages
project state (issues, boards, milestones, worktrees) but never modifies application
code, tests, or documentation. User-triggered only - never activates automatically.

## Prerequisites

Requires an authenticated `gh` CLI and a git repo with a configured remote.

## Procedure

- **Load agent persona:** load the `vaultspec-project-coordinator` persona. Gather
  current project state from GitHub (issues, milestones, GitHub Projects, labels) and
  local state (branches, worktrees, recent commits).

- **Synthesize and present:** summarise the state. Identify blockers, priorities, and
  gaps.

- **Query-response cycle:** enter the interaction loop. Gather relevant state via `gh`
  and `git`. Present proposed actions with exact CLI invocations. On approval, execute
  and confirm results. All proposals are subject to the operating principles defined in
  the agent persona.

## Agent persona

Load the `vaultspec-project-coordinator` agent persona for all project management work.
The persona operates only on project management surfaces: issues, boards, milestones,
labels, worktrees, and status reporting. It must not modify application code,
`.vaultspec/`, or `.vault/` contents.

The persona defines detailed capabilities, operating principles, and hard boundaries.
The skill writes no vault record. All context is gathered and presented within the
session.
