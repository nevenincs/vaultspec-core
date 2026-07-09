---
generated: true
tags:
  - '#index'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - '[[2026-07-09-mcp-tool-schema-P01-S01]]'
  - '[[2026-07-09-mcp-tool-schema-P01-S02]]'
  - '[[2026-07-09-mcp-tool-schema-P01-S03]]'
  - '[[2026-07-09-mcp-tool-schema-P01-S04]]'
  - '[[2026-07-09-mcp-tool-schema-P01-S05]]'
  - '[[2026-07-09-mcp-tool-schema-P02-S06]]'
  - '[[2026-07-09-mcp-tool-schema-P02-S07]]'
  - '[[2026-07-09-mcp-tool-schema-P02-S08]]'
  - '[[2026-07-09-mcp-tool-schema-P02-S09]]'
  - '[[2026-07-09-mcp-tool-schema-P02-S10]]'
  - '[[2026-07-09-mcp-tool-schema-adr]]'
  - '[[2026-07-09-mcp-tool-schema-plan]]'
  - '[[2026-07-09-mcp-tool-schema-reference]]'
  - '[[2026-07-09-mcp-tool-schema-research]]'
---

# `mcp-tool-schema` feature index

Auto-generated index of all documents tagged with `#mcp-tool-schema`.

## Documents

### adr

- `2026-07-09-mcp-tool-schema-adr` - `mcp-tool-schema` adr: tiered hot-tool surface with a stateless discover/invoke gateway | (**status:** `accepted`)

### exec

- `2026-07-09-mcp-tool-schema-P01-S01` - Create the vaultcore edit-engine module: move \_resolve_doc_path, \_split_document, \_enforce_blob_hash, \_compose_new_text, \_validate_proposed, \_write_proposed, and \_EditError verbatim, and add a result-returning execute_edit core plus a typed EditResult dataclass (status, path, blob_hash, error, warnings) with no Typer or console coupling (agent: vaultspec-high-executor)
- `2026-07-09-mcp-tool-schema-P01-S02` - Re-point cmd_set_body, cmd_set_frontmatter, and cmd_edit at the extracted engine as thin renderers that call execute_edit and render the canonical envelope via \_emit, deleting the now-migrated helper bodies (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P01-S03` - Add a single kebab-case feature-and-tag normalizer to vaultcore that strips a leading hash, lowercases, rejects path-traversal, and validates the canonical pattern, returning a typed result (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P01-S04` - Re-point cmd_add feature and tag validation at the new normalizer, deleting the inline regex copy so the CLI and the MCP surface share one validator (agent: vaultspec-low-executor)
- `2026-07-09-mcp-tool-schema-P01-S05` - Add WorkspaceFactory edit-engine unit tests (resolve, blob-hash conflict, compose, validate-refusal, write) and the normalizer tests, and confirm the existing set-body/set-frontmatter/edit CLI tests stay green (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P02-S06` - Add the shared per-item result envelope module: a build helper producing the canonical item shape (index, target, status of created/updated/unchanged/failed, path, blob_hash, structured error, warnings) and an aggregate reducer returning ok/mixed/failed, matching the CLI sync-envelope vocabulary (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P02-S07` - Rebuild create as a batch-native tool: delete the inline hydrate/filename/atomic_write path, normalize each spec via the shared normalizer, resolve_related_inputs, validate_feature_dependencies against vault state including earlier same-batch items, call create_vault_doc per item, then generate_feature_index for affected features, emitting the shared per-item envelope (agent: vaultspec-high-executor)
- `2026-07-09-mcp-tool-schema-P02-S08` - Implement the new edit tool: batch body-prose operations (append_section, replace_section, set_body) addressed by stem or path, each composing the full body and flowing through the extracted execute_edit engine with the optional expected_blob_hash guard and the post-write blob_hash in the per-item result, section miss reported as section_not_found (agent: vaultspec-high-executor)
- `2026-07-09-mcp-tool-schema-P02-S09` - Add WorkspaceFactory tests for batch create: intra-batch lifecycle dependency validation, per-item partial-failure envelope, and automatic feature-index regeneration for affected features (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P02-S10` - Add WorkspaceFactory tests for the edit tool: the blob-hash conflict path, intra-batch same-document sequencing with the hash set on the first op only, section_not_found, and the post-write hash chaining from one op to the next (agent: vaultspec-standard-executor)

### plan

- `2026-07-09-mcp-tool-schema-plan` - `mcp-tool-schema` plan

### reference

- `2026-07-09-mcp-tool-schema-reference` - `mcp-tool-schema` reference: implementation reconciliation against the current MCP server

### research

- `2026-07-09-mcp-tool-schema-research` - `mcp-tool-schema` research: grounding a progressive-discovery MCP tool surface for vaultspec-core
