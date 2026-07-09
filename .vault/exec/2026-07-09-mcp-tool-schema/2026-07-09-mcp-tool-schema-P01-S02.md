---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S02'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Re-point cmd_set_body, cmd_set_frontmatter, and cmd_edit at the extracted engine as thin renderers that call execute_edit and render the canonical envelope via \_emit, deleting the now-migrated helper bodies (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/cli/edit_cmd.py`

## Description

- Import the moved helpers and `execute_edit` from the new engine into the edit command, aliasing the engine error back to the existing internal name so the rename machinery keeps working.
- Delete the migrated helper bodies from the edit command, leaving only the Typer wiring, the body-channel reader, the related resolver, the `_emit` renderer, and the rename verb.
- Rewrite `_execute_edit` as a thin wrapper that calls `execute_edit` on the current target root and hands the typed result to a new `_render_edit_result` seam.
- Map the typed result back to the exact shipped `set-body` / `set-frontmatter` / `edit` envelopes and exit codes, mirroring how the status verb renders over the orientation core.

## Outcome

- `cmd_set_body`, `cmd_set_frontmatter`, and `cmd_edit` are thin renderers over `execute_edit`; envelopes, output, and exit codes are byte-preserved and the pre-existing edit and rename CLI tests stay green.

## Notes

- The rename verb reuses the same moved helpers, so it now imports them from the engine as well; no behavior change to rename.
