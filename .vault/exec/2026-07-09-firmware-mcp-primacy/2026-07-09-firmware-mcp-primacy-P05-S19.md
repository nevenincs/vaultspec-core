---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S19'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Run vaultspec-core vault check all and confirm clean, regenerating the feature index if warned

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Run `vaultspec-core spec doctor`; every diagnosis line reports `ok`, including builtins current and rename integrity.
- Run `vaultspec-core vault check all`; all structural, frontmatter, link, and reference checks report clean.
- Run `vaultspec-core vault check all --feature firmware-mcp-primacy`; every check reports clean for this feature.

## Outcome

Spec doctor is fully clean with no drift, no stale copies, and no failures. The feature-scoped vault check is entirely clean. The unscoped vault check surfaces three warnings, all belonging to other features: `codebase-drift-sweep` has a plan but no ADR, and two unrelated plans (`cli-reference-automation`, `codebase-drift-sweep`) lack research references. None of these touch firmware-mcp-primacy, whose documents pass cleanly.

## Notes

The three warnings are pre-existing and out of scope for this feature; they were not introduced by the reword and are left untouched.
