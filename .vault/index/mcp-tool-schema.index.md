---
generated: true
tags:
  - '#index'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
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
  - '[[2026-07-09-mcp-tool-schema-P03-S11]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S12]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S13]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S14]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S15]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S16]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S17]]'
  - '[[2026-07-09-mcp-tool-schema-P03-S18]]'
  - '[[2026-07-09-mcp-tool-schema-P04-S19]]'
  - '[[2026-07-09-mcp-tool-schema-P04-S20]]'
  - '[[2026-07-09-mcp-tool-schema-P04-S21]]'
  - '[[2026-07-09-mcp-tool-schema-P04-S22]]'
  - '[[2026-07-09-mcp-tool-schema-P04-S23]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S24]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S25]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S26]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S27]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S28]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S29]]'
  - '[[2026-07-09-mcp-tool-schema-P05-S30]]'
  - '[[2026-07-09-mcp-tool-schema-adr]]'
  - '[[2026-07-09-mcp-tool-schema-audit]]'
  - '[[2026-07-09-mcp-tool-schema-plan]]'
  - '[[2026-07-09-mcp-tool-schema-reference]]'
  - '[[2026-07-09-mcp-tool-schema-research]]'
---

# `mcp-tool-schema` feature index

Auto-generated index of all documents tagged with `#mcp-tool-schema`.

## Documents

### adr

- `2026-07-09-mcp-tool-schema-adr` - `mcp-tool-schema` adr: tiered hot-tool surface with a stateless discover/invoke gateway | (**status:** `accepted`)

### audit

- `2026-07-09-mcp-tool-schema-audit` - `mcp-tool-schema` audit: `nine-tool MCP server rebuild review`

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
- `2026-07-09-mcp-tool-schema-P03-S11` - Add the shared plan resolver: resolve a feature tag or plan stem to a single plan document via vaultcore.query.list_documents, raising a typed ambiguity error when a feature maps to more than one plan (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S12` - Extend find: add resource_link result entries for document bodies with the inline body flag as fallback, add per-document blob_hash in document-search mode, route feature-listing status enrichment through vaultcore.orientation instead of \_infer_status, and declare the outputSchema return type (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S13` - Add the status tool over vaultcore.orientation: compute_rollup for the unparameterized orientation view and compute_trace for a feature-or-plan target, returning the feature inventory, in-flight plans with tier and completion, next open step, and the tool-schema package version as structured content (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S14` - Add the check tool over vaultcore.checks: run the check suite with an optional fix flag and return structured findings, annotated read-only without fix and non-read-only idempotent with fix (agent: vaultspec-low-executor)
- `2026-07-09-mcp-tool-schema-P03-S15` - Add the plan_progress tool: mark a batch of canonical step ids checked or unchecked (explicit states only, no toggle) via plan.commands.step_ops against a plan resolved by the shared resolver, returning updated completion counts and the next open step (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S16` - Add the plan_edit tool: an operation list of add, insert, edit, and remove carrying the action-plus-scope shape, routed through the plan step verb logic that owns canonical identifiers and gap-no-reuse, against a resolver-addressed plan (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S17` - Add WorkspaceFactory tests for find-extend and the status and check tools: resource_link and blob_hash presence, orientation-sourced status, rollup and trace shape, and check findings with and without fix (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P03-S18` - Add WorkspaceFactory tests for plan_progress, plan_edit, and the resolver: checked/unchecked batch marking, step add/insert/edit/remove identifier preservation, and the ambiguous-feature resolution error (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P04-S19` - Add the catalog module: parse the command inventory between the vaultspec:generated markers in the CLI reference at server start into an in-memory structure of verb paths, descriptions, and parameter schemas, applying the static denylist (uninstall, MCP registry mutation, index hand-authoring) at parse time (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P04-S20` - Add the discover tool: rank the parsed catalog over a query across verb paths and descriptions and return the ranked verb paths with their full parameter schemas, loaded into context only on demand, annotated read-only and idempotent (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P04-S21` - Add the invoke tool: validate the verb path and argument object against the parsed inventory and denylist, build an argv list (never a shell), inject --target from the resolved root_dir, pass --json where the verb supports it, run the installed vaultspec-core binary with a timeout, fold stderr into the error payload, and return parsed JSON or captured stdout, annotated destructive (agent: vaultspec-high-executor)
- `2026-07-09-mcp-tool-schema-P04-S22` - Add WorkspaceFactory tests for the catalog: marker parsing yields the expected verb paths and schemas, and denylisted verbs are absent from both discover results and invoke acceptance (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P04-S23` - Add tests for the gateway executor against the real uv run --no-sync vaultspec-core binary, covering a read-only verb returning parsed JSON, an unknown verb path rejected before spawn, a nonzero exit folding stderr into the error payload, and the discover ranking order (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P05-S24` - Migrate whole-call failures across every tool handler from the success-dict idiom to protocol isError, raising through FastMCP for invalid arguments, unknown verbs, and unresolvable targets while keeping per-item status only inside batch result arrays (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P05-S25` - Declare outputSchema and return structuredContent via FastMCP return-type derivation on all nine tools, replacing loose dict returns with typed result models (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P05-S26` - Correct the ToolAnnotations per ADR Q6: fix create's wrong idempotent hint to non-idempotent, mark edit and plan_edit and invoke destructive, keep plan_progress idempotent with explicit checked/unchecked only, and set status/find/discover read-only idempotent (agent: vaultspec-low-executor)
- `2026-07-09-mcp-tool-schema-P05-S27` - Wrap every new handler in \_isolated_context and extend the server instructions string to name the nine-tool surface and the tool-schema version, registering all tools through the updated register_tools bootstrap (agent: vaultspec-low-executor)
- `2026-07-09-mcp-tool-schema-P05-S28` - Audit and tighten the hot-verb help strings in the CLI reference so the discover payload reads well verbatim, regenerating the inventory between the vaultspec:generated markers (agent: vaultspec-low-executor)
- `2026-07-09-mcp-tool-schema-P05-S29` - Add the nine-tool integration test asserting registration of all nine tools, outputSchema presence, corrected annotations, and isError on a whole-call failure (agent: vaultspec-standard-executor)
- `2026-07-09-mcp-tool-schema-P05-S30` - Review the full nine-tool surface for ADR and reference fidelity: owning-verb routing, isError and envelope contract, annotations, and the subprocess injection guard (agent: vaultspec-code-reviewer)

### plan

- `2026-07-09-mcp-tool-schema-plan` - `mcp-tool-schema` plan

### reference

- `2026-07-09-mcp-tool-schema-reference` - `mcp-tool-schema` reference: implementation reconciliation against the current MCP server

### research

- `2026-07-09-mcp-tool-schema-research` - `mcp-tool-schema` research: grounding a progressive-discovery MCP tool surface for vaultspec-core
