---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S10'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory tests for the edit tool: the blob-hash conflict path, intra-batch same-document sequencing with the hash set on the first op only, section_not_found, and the post-write hash chaining from one op to the next (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_edit_tool.py`

## Description

- Add the batch edit tests driving the real FastMCP server over the in-memory session transport with zero mocks.
- Cover the blob-hash conflict path: a stale expected hash fails the item as a conflict and leaves the file untouched.
- Cover section_not_found for a heading that does not exist, reported as a per-item failure rather than a whole-call error.
- Cover intra-batch same-document sequencing with the hash set on the first op only, and the post-write hash chaining from one op into a later guarded op.
- Cover set_body returning the true post-write blob hash, the empty-batch protocol error, and an unresolvable-target per-item failure.

## Outcome

- Seven edit tests pass on the real filesystem, proving optimistic-concurrency, section addressing, and hash chaining with no test doubles.

## Notes

- The conflict test constructs a deliberately stale git blob OID and asserts the on-disk bytes are unchanged, so the guard is proven to refuse before any write.
