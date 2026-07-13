---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S24'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Propagate firmware edits with vaultspec-core sync and confirm mirrors regenerate clean

## Scope

- `.claude/rules/vaultspec-cli.builtin.md`

## Description

- Re-seed the builtin edit into the installed workspace with `install --upgrade`
  (2 updated: the CLI rule and the reference; 40 unchanged).
- Run `vaultspec-core sync` and confirm every provider mirror is up to date.

## Outcome

The rename verb is present in the shipped builtins, the installed `.vaultspec/`
workspace, and all four provider mirrors; sync reports them clean.

## Notes

Provider mirror directories are gitignored and regenerated, so only the builtin source
and the two tracked `.vaultspec/` copies appear as committed firmware changes.
