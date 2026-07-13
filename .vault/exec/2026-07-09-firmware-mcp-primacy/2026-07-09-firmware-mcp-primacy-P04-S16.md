---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S16'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Regenerate the bundled CLI reference via vaultspec-core spec reference generate so the new header prose lands while the generated command-inventory marker block stays byte-identical

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Ran `vaultspec-core spec reference generate` to rewrite the generator-owned regions of the bundled reference after the header prose edit.
- Confirmed via git diff that the only change is the six-line prose insertion above the marker block and that the generated command-inventory block is byte-identical.
- Propagated the regenerated reference into this repo's `.vaultspec/reference/cli.md` with `vaultspec-core install --upgrade` (1 updated, 44 unchanged) so the source and synced copies stay in lockstep.

## Outcome

The bundled reference and the `.vaultspec` synced copy are byte-identical and carry the new dual-role paragraph. The generated command-inventory marker block did not move; the MCP gateway's verb catalog is unchanged before and after.

## Notes

Sync does not propagate the reference document; `install --upgrade` is the re-seed path for `.vaultspec/reference/cli.md`. Both the builtin source and the synced copy are staged together so `spec doctor` and prek do not flag drift.
