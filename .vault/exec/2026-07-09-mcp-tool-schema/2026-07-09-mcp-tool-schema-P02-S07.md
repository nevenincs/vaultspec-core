---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S07'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Rebuild create as a batch-native tool: delete the inline hydrate/filename/atomic_write path, normalize each spec via the shared normalizer, resolve_related_inputs, validate_feature_dependencies against vault state including earlier same-batch items, call create_vault_doc per item, then generate_feature_index for affected features, emitting the shared per-item envelope (agent: vaultspec-high-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Delete the inline hydrate, filename, atomic_write, and post-write validate path from the old create tool in `vault_tools.py`, leaving only find there.
- Create the `tools` package and author the batch-native create tool in `tools/documents.py` as a thin sequential loop over the owning cores.
- Per item: normalize the feature via the shared normalizer, reject the index type, resolve related references, validate feature dependencies against the on-disk vault including earlier same-batch items, then scaffold through create_vault_doc.
- Default the plan tier to L1 and validate it, mirroring the CLI vault add default, so plan scaffolds pass the framework frontmatter validator.
- Append optional seed prose as a Context section by routing a full-body recompose through the shared edit engine, authoring no write logic in the tool layer.
- Regenerate the affected feature indexes once at the end of the batch via generate_feature_index over a cache-bypassed graph.
- Wire register_document_tools into the server bootstrap alongside find, and annotate create non-read-only, non-destructive, non-idempotent.

## Outcome

- Create contains no inline creation path and routes every mutation through create_vault_doc plus generate_feature_index; the batch envelope reports per-item outcomes and the feature index regenerates as an automatic side effect.

## Notes

- The plan template requires a tier; the batch spec gained an optional tier field defaulting to L1, since a plan scaffolded without one fails its own frontmatter validator.
