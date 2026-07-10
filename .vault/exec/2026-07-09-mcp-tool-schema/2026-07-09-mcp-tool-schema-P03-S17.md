---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S17'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory tests for find-extend and the status and check tools: resource_link and blob_hash presence, orientation-sourced status, rollup and trace shape, and check findings with and without fix (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_orientation_tools.py`

## Description

- Add the orientation-tools test module driving the real FastMCP server over the in-memory session transport against a WorkspaceFactory-installed vault, with no mocks, stubs, or skips.
- Cover the find-extend contract: a document-search row carries a `resource_uri` and a blob hash matching the true git blob object id of the on-disk bytes, and a feature with an ADR and a plan reads back as the orientation-sourced `Planned` status.
- Cover `status`: the rollup lists features and echoes the tool-schema version and carries no blob hashes; a feature target returns a trace over its plan; an unresolvable target is a protocol error.
- Cover `check`: a fresh vault is clean, a document with a dangling wiki-link raises error findings including the dangling checker, and the fix flag runs and is reported.

## Outcome

- Real-filesystem, zero-mock coverage of the find-extend, status, and check tools, all green.

## Notes

- Sidestepped the repo-wide broken `tmp_path` shim by using the WorkspaceFactory-over-tempfile `vault_root` fixture, as the surrounding batch tests do.
