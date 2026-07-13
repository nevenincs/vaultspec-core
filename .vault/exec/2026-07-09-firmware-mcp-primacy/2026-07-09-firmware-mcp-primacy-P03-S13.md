---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S13'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Apply the capability-first pass over the docs-curator's seven CLI references, retaining every verb and leaving the tools allowlist byte-identical

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`

## Description

- Apply the capability-first pass over the docs-curator's CLI references, retaining every verb and the byte-identical tools allowlist.
- Reorder the mechanical-hygiene reference to lead with the capability (cede hygiene) then the vault check all fix verb.
- Reorder the ADR-set reference to lead with inventory then the vault list adr verb.
- Reorder the topology reference to lead with mapping the supersession graph then the vault graph verb.
- Leave the already capability-first references (supersede, mutators, verify loop, audit scaffold) intact.

## Outcome

- The docs-curator's verb-first references now lead with capability; every CLI verb is retained and the allowlist is byte-identical.

## Notes

- The curator persona was already largely capability-worded, so the pass was three surgical reorders rather than a rewrite.
