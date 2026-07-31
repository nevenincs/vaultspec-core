---
tags:
  - '#exec'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:d987379a9cb13d09c359ebc32c9fc6dcd9af57aebbbf2dad3af96d0446f2a3b7'
step_id: 'S05'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
---

# Document the infix form for the narrative trio in the firmware filename patterns and regenerate the bundled CLI reference

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Extend the audit-infix sentence in the vaultspec rule to the narrative trio
  and add the infix pattern to the File names conventions; roll out via install
  upgrade and sync; run the reference generator.

## Outcome

Firmware documents the trio-wide convention. The generated CLI reference is
command-level (no per-flag inventory), so the generator correctly reports up to
date and the drift test passes. Modified:
`src/vaultspec_core/builtins/rules/vaultspec.builtin.md` (+ CLI-written mirror).

## Notes

None.
