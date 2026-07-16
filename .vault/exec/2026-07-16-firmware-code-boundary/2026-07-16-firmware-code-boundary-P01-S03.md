---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S03'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# Add the one-clause hierarchy statement that source code sits outside the documentation hierarchy and never references vault or harness contents

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Extend the Documentation Hierarchy intro in
  `src/vaultspec_core/builtins/rules/vaultspec.builtin.md` with the clause placing
  source code outside the hierarchy, stating the one-way locator direction, and naming
  commit trailers as the sanctioned linkage channel.
- Propagate with install upgrade and sync to `.vaultspec/rules/vaultspec.builtin.md`.

## Outcome

The always-on vaultspec rule now closes the previously implicit gap: the hierarchy
prose states explicitly that tracked source-file content never references `.vault/`
documents, identifiers, or harness contents. Modified files:
`src/vaultspec_core/builtins/rules/vaultspec.builtin.md`,
`.vaultspec/rules/vaultspec.builtin.md`.

## Notes

None.
