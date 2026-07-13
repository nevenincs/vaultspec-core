---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S06'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the shared per-item result envelope module: a build helper producing the canonical item shape (index, target, status of created/updated/unchanged/failed, path, blob_hash, structured error, warnings) and an aggregate reducer returning ok/mixed/failed, matching the CLI sync-envelope vocabulary (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/results.py`

## Description

- Add the `results` module holding the unified per-item batch envelope shared by the `create` and `edit` tools.
- Define the `ItemResult` Pydantic model carrying index, target, status, path, blob_hash, structured error, and warnings.
- Define the `BatchResult` Pydantic model carrying the aggregate status plus the item list, so FastMCP derives an outputSchema from the tool return type.
- Add the `build_item` assembler, the `reduce_status` aggregator, and the `build_batch` wrapper.
- Map the aggregate to the CLI sync-envelope vocabulary: all-success is ok, all-failure is failed, any disagreement is mixed, treating unchanged as a successful no-op.

## Outcome

- The `results` module publishes `ItemResult`, `BatchResult`, `build_item`, `reduce_status`, and `build_batch`; both batch tools import it and FastMCP derives structured output from the model return type.

## Notes

- The reducer counts created, updated, and unchanged as successes so an idempotent no-op edit never drags a batch to mixed.
