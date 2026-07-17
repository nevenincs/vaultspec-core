---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Open feature branch and draft PR referencing the venv-corruption incident and the ADR amendment

## Scope

- `repo workflow`

## Description

- Branch feat/mcp-static-launch created from origin/main, keeping the
  in-flight watchdog-parity branch (8 unmerged commits) independent.
- Commit the pipeline documents (research, ADR, plan, index) plus a
  gitignore entry for the local .qdrant-initialized marker, following the
  mcp-ownership gitignore precedent.
- Push and open draft PR 224 with the plan checklist mirrored in the body.

## Outcome

Draft PR 224 open at commit 629f5784; plan and grounding documents are on
the branch; the worktree carries no foreign changes.

## Notes

First commit attempt failed hooks: mdformat-check on two vault documents and
MD001 from a missing Steps heading above the Phase blocks (removed as
scaffold residue, actually load-bearing). Restored the heading, formatted
with the venv mdformat, recommitted clean.
