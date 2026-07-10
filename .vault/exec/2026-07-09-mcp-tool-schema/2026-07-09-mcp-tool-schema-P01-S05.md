---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S05'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory edit-engine unit tests (resolve, blob-hash conflict, compose, validate-refusal, write) and the normalizer tests, and confirm the existing set-body/set-frontmatter/edit CLI tests stay green (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/vaultcore/test_edit_engine.py`

## Description

- Add a WorkspaceFactory-backed vault fixture over a stdlib tempfile root that seeds two valid documents and initializes the global path context.
- Cover resolve for a stem and the typed error for an unknown reference.
- Cover the blob-hash guard raising the typed conflict, a matching guard being a no-op, and `execute_edit` folding a stale hash into a failed result.
- Cover compose preserving the body and refreshing the modified stamp, validate-refusal leaving the file unchanged, the round-trip set-body update-then-unchanged, a matching-guard write, dry-run writing nothing, and the direct write helper.
- Add normalizer tests for hash-strip, lowercase, digits, empty rejection, path-traversal rejection, interior whitespace and underscore rejection, and the label-scoped message.

## Outcome

- Twenty new tests pass on the real filesystem with zero mocks; the pre-existing set-body, set-frontmatter, and edit CLI tests remain green; the full unit gate passes at 1591 tests.

## Notes

- The fixture writes documents with explicit LF newlines and uses tempfile plus WorkspaceFactory rather than `tmp_path`, since the repository's Windows temp-compat shim breaks the `tmp_path` fixture under the top-level test tree.
