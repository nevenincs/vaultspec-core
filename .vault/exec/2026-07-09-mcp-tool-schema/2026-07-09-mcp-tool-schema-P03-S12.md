---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S12'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Extend find: add resource_link result entries for document bodies with the inline body flag as fallback, add per-document blob_hash in document-search mode, route feature-listing status enrichment through vaultcore.orientation instead of \_infer_status, and declare the outputSchema return type (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Relocate the `find` tool out of the old vault-tools module into the documents tool module and register it through `register_document_tools`, matching the plan's file scope.
- Add a per-document `blob_hash` (the git blob object id of the on-disk bytes) and a `resource_uri` resource-link to every document-search row, keeping the inline body as the request-only fallback.
- Route the feature-listing lifecycle status through the orientation core by pairing `compute_rollup` with a new `feature_lifecycle_status` helper, and delete the local `_infer_status` inference.
- Declare the tool output schema by returning a typed `FindEntry` list, and extract the concurrent-request isolation wrapper into a shared isolation module so the three tool modules share one definition.
- Delete the migrated vault-tools module and rewire the server bootstrap.

## Outcome

- `find` returns a per-document blob hash and a resource link, sources lifecycle status from orientation, and declares a structured output schema; the second status inference in the MCP layer is gone.

## Notes

- FastMCP evaluates tool annotations at runtime, so `Context` must stay a runtime import; extended the project's documented per-file TC002 ignore to the two new tool modules and dropped the deleted module's stale entry.
