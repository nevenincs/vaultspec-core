---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S22'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory tests for the catalog: marker parsing yields the expected verb paths and schemas, and denylisted verbs are absent from both discover results and invoke acceptance (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_catalog.py`

## Description

- Add the catalog test module building the catalog from the real CLI reference shipped into a WorkspaceFactory-installed vault over a stdlib tempfile root, with no mocks, stubs, or skips.
- Assert the marker block yields expected hot and long-tail verb paths and a non-trivial catalog size, and that a cataloged verb carries its curated description, its declared flags, correct value-versus-boolean flag typing, and `--json` support.
- Assert every denylisted verb is absent from entries yet reported by `is_denied`, that the specific ADR-named classes are denied while read-only MCP-registry inspection stays reachable, and that a denied verb never surfaces through the ranking.
- Assert the ranking surfaces a known verb for its intent with non-increasing scores, and that a reference without the generated markers raises a loud `ValueError`.

## Outcome

- Six catalog tests pass, covering marker parsing, flag and `--json` schema enrichment, denylist exclusion and reporting, ranking, and marker-absence failure.

## Notes

- No blockers.
