---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S08'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Implement the new edit tool: batch body-prose operations (append_section, replace_section, set_body) addressed by stem or path, each composing the full body and flowing through the extracted execute_edit engine with the optional expected_blob_hash guard and the post-write blob_hash in the per-item result, section miss reported as section_not_found (agent: vaultspec-high-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Author the batch-native edit tool in `tools/documents.py` over the extracted execute_edit engine.
- Model each operation as append_section, replace_section, or set_body against a target addressed by stem or path, with an optional expected_blob_hash guard.
- Resolve the target with the same reference resolution the edit engine uses, then split the on-disk body and compose the full new body for the section op.
- Address sections by exact heading-line text, first match, bounding a section at the next heading of the same or a higher level; a miss is a per-item section_not_found failure that never calls the engine.
- Route every write through execute_edit so the concurrency guard, pre-write conformance checks, modified-stamp refresh, and post-write blob hash apply uniformly, and map the EditResult onto the shared per-item envelope.
- Annotate edit non-read-only, destructive, non-idempotent, and keep the isolation wrapper on the handler.

## Outcome

- The edit tool enforces expected_blob_hash, returns the post-write blob_hash for chaining, reports section_not_found per item, never touches frontmatter or filenames, and shares the create envelope shape.

## Notes

- Section composition reads and splits the body in the tool, but the actual write and hash guard stay in the shared engine, so no edit logic is reimplemented here; intra-batch sequencing works because each op reads the on-disk bytes the previous op produced.
