---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S09'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Harden atomic provider configuration writes against pre-existing sibling nodes

## Scope

- `src/vaultspec_core/core/helpers.py`
- `src/vaultspec_core/core/gitignore.py`
- `src/vaultspec_core/core/gitattributes.py`
- `src/vaultspec_core/core/tests/test_atomic_write.py`
- `src/vaultspec_core/core/tests/test_resource_rename.py`
- `src/vaultspec_core/tests/cli/test_gitignore.py`
- `src/vaultspec_core/tests/cli/test_gitattributes.py`
- `src/vaultspec_core/tests/cli/test_sync_parse.py`

## Description

- Replace PID-derived scratch names with short, unpredictable sibling names opened
  exclusively through a file descriptor.
- Write, flush, retain an existing regular destination mode, and synchronize bytes
  through the descriptor before atomic replacement.
- Verify the scratch node identity before promotion and cleanup; fail closed when
  replacement cannot remain atomic.
- Route UTF-8, BOM-preserving `.gitignore`, and BOM-preserving `.gitattributes` writes
  through the shared byte writer used by MCP JSON, Codex TOML, and ownership callers.
- Exercise regular-file, relative-link, broken-link, directory, destination-link,
  missing-parent, long-name, managed-file, resource-rename, and MCP lifecycle behavior
  on the real filesystem.

## Outcome

- The writer never selects or removes the legacy predictable sibling node and never
  follows a destination link during replacement.
- Focused writer, managed-file, resource-rename, and MCP gates passed 138 tests on
  Windows.
- The clean external-basetemp repository unit ledger passed all 1,773 selected tests
  with 1,052 deliberate deselections. Ruff, format, and Ty passed across the
  repository.
- Source and wheel artifacts built successfully and passed the isolated import,
  metadata, entry-point, server-factory, and CLI smoke script.
- An isolated wheel installation wrote `.mcp.json` and `.codex/config.toml`; the real
  Claude CLI reported the project entry pending approval and the real Codex CLI returned
  the expected enabled stdio definition.

## Notes

The two resource-rename tests that used the predictable scratch name as an induced
failure could not retain that trigger after the defect was removed. They now prove the
operator node survives successful writes. Reverse-journal rollback remains covered by
the dedicated rename transaction and feature-rename suites; this step does not claim
those converted cases as rollback tests.
