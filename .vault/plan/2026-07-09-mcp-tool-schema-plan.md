---
tags:
  - '#plan'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
tier: L2
related:
  - '[[2026-07-09-mcp-tool-schema-adr]]'
  - '[[2026-07-09-mcp-tool-schema-reference]]'
  - '[[2026-07-09-mcp-tool-schema-research]]'
---

# `mcp-tool-schema` plan

Rebuild the vaultspec-core MCP server into the accepted nine-tool tiered surface by converging every mutation onto the shared cores that already exist, with one blocking edit-engine extraction ahead of the tool work.

## Description

This plan implements the accepted `mcp-tool-schema` ADR and its reconciliation reference. The MCP server currently exposes two tools (`find`, `create`) whose `create` reimplements filename generation, hydration, and validation in parallel to the owning core. The redesign replaces that pair with nine first-class tools: the hot-path set (`status`, `find`, `create`, `edit`, `plan_progress`, `plan_edit`, `check`) plus the stateless `discover`/`invoke` gateway, all on the SDK-bundled FastMCP (`mcp>=1.26.0`) with no standalone `fastmcp`.

The reference fixes the dependency order and the disposition of every current asset. The shared-core layer the ADR presumes already exists for four of the five mutation domains: `vaultcore.hydration.create_vault_doc` owns creation, `plan.commands.step_ops` plus `plan.parser` own plan structure, `vaultcore.orientation` owns status rollups, and `vaultcore.checks` owns validation. Only the body-edit pipeline is missing from the shared layer, living as Typer-free helpers inside the edit command; extracting it is the one blocking refactor. The `create` tool is the single true drift casualty and is rebuilt onto the core. Hot tools dispatch in-process to those cores; the gateway `invoke` subprocesses the installed `vaultspec-core` binary as a validated argv list, the only disposition that covers the long-tail verbs without unbounded plumbing.

No new creation, edit, or plan-mutation logic is authored inside `mcp_server`; every mutation routes through the owning verb logic. Batch tools adopt the CLI's shipped blob-hash optimistic-concurrency contract and its canonical status vocabulary, so the MCP surface and the CLI speak one result language. Grounding: see the ADR and the reconciliation reference named in the `related:` frontmatter.

## Steps

### Phase `P01` - Shared-core extraction (blocking)

Extract the body-edit pipeline out of the Typer-coupled edit command into a vaultcore edit-engine returning typed results, and consolidate the triplicated kebab-case validator into one normalizer, so every downstream MCP tool converges on shared cores. This Phase blocks all others.

- [x] `P01.S01` - Create the vaultcore edit-engine module: move \_resolve_doc_path, \_split_document, \_enforce_blob_hash, \_compose_new_text, \_validate_proposed, \_write_proposed, and \_EditError verbatim, and add a result-returning execute_edit core plus a typed EditResult dataclass (status, path, blob_hash, error, warnings) with no Typer or console coupling (agent: vaultspec-high-executor); `src/vaultspec_core/vaultcore/edit_engine.py`.
- [x] `P01.S02` - Re-point cmd_set_body, cmd_set_frontmatter, and cmd_edit at the extracted engine as thin renderers that call execute_edit and render the canonical envelope via \_emit, deleting the now-migrated helper bodies (agent: vaultspec-standard-executor); `src/vaultspec_core/cli/edit_cmd.py`.
- [x] `P01.S03` - Add a single kebab-case feature-and-tag normalizer to vaultcore that strips a leading hash, lowercases, rejects path-traversal, and validates the canonical pattern, returning a typed result (agent: vaultspec-standard-executor); `src/vaultspec_core/vaultcore/normalize.py`.
- [x] `P01.S04` - Re-point cmd_add feature and tag validation at the new normalizer, deleting the inline regex copy so the CLI and the MCP surface share one validator (agent: vaultspec-low-executor); `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S05` - Add WorkspaceFactory edit-engine unit tests (resolve, blob-hash conflict, compose, validate-refusal, write) and the normalizer tests, and confirm the existing set-body/set-frontmatter/edit CLI tests stay green (agent: vaultspec-standard-executor); `tests/unit/vaultcore/test_edit_engine.py`.

### Phase `P02` - create rebuild and edit tool

Delete the inline create reimplementation and rebuild it batch-native over create_vault_doc plus feature-index regeneration, and add the new batch body-prose edit tool over the extracted edit-engine with the blob-hash optimistic-concurrency guard, on a shared per-item result envelope.

- [x] `P02.S06` - Add the shared per-item result envelope module: a build helper producing the canonical item shape (index, target, status of created/updated/unchanged/failed, path, blob_hash, structured error, warnings) and an aggregate reducer returning ok/mixed/failed, matching the CLI sync-envelope vocabulary (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/results.py`.
- [x] `P02.S07` - Rebuild create as a batch-native tool: delete the inline hydrate/filename/atomic_write path, normalize each spec via the shared normalizer, resolve_related_inputs, validate_feature_dependencies against vault state including earlier same-batch items, call create_vault_doc per item, then generate_feature_index for affected features, emitting the shared per-item envelope (agent: vaultspec-high-executor); `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `P02.S08` - Implement the new edit tool: batch body-prose operations (append_section, replace_section, set_body) addressed by stem or path, each composing the full body and flowing through the extracted execute_edit engine with the optional expected_blob_hash guard and the post-write blob_hash in the per-item result, section miss reported as section_not_found (agent: vaultspec-high-executor); `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `P02.S09` - Add WorkspaceFactory tests for batch create: intra-batch lifecycle dependency validation, per-item partial-failure envelope, and automatic feature-index regeneration for affected features (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_create_tool.py`.
- [x] `P02.S10` - Add WorkspaceFactory tests for the edit tool: the blob-hash conflict path, intra-batch same-document sequencing with the hash set on the first op only, section_not_found, and the post-write hash chaining from one op to the next (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_edit_tool.py`.

### Phase `P03` - find extend and thin-wrapper tools

Extend find with resource_link and per-document blob_hash routed through orientation, and add the status, check, plan_progress, and plan_edit thin wrappers over vaultcore.orientation, vaultcore.checks, and plan.commands.step_ops, plus a shared feature-or-stem plan resolver.

- [x] `P03.S11` - Add the shared plan resolver: resolve a feature tag or plan stem to a single plan document via vaultcore.query.list_documents, raising a typed ambiguity error when a feature maps to more than one plan (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/plan_resolver.py`.
- [x] `P03.S12` - Extend find: add resource_link result entries for document bodies with the inline body flag as fallback, add per-document blob_hash in document-search mode, route feature-listing status enrichment through vaultcore.orientation instead of \_infer_status, and declare the outputSchema return type (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `P03.S13` - Add the status tool over vaultcore.orientation: compute_rollup for the unparameterized orientation view and compute_trace for a feature-or-plan target, returning the feature inventory, in-flight plans with tier and completion, next open step, and the tool-schema package version as structured content (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `P03.S14` - Add the check tool over vaultcore.checks: run the check suite with an optional fix flag and return structured findings, annotated read-only without fix and non-read-only idempotent with fix (agent: vaultspec-low-executor); `src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `P03.S15` - Add the plan_progress tool: mark a batch of canonical step ids checked or unchecked (explicit states only, no toggle) via plan.commands.step_ops against a plan resolved by the shared resolver, returning updated completion counts and the next open step (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools/plan.py`.
- [x] `P03.S16` - Add the plan_edit tool: an operation list of add, insert, edit, and remove carrying the action-plus-scope shape, routed through the plan step verb logic that owns canonical identifiers and gap-no-reuse, against a resolver-addressed plan (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools/plan.py`.
- [x] `P03.S17` - Add WorkspaceFactory tests for find-extend and the status and check tools: resource_link and blob_hash presence, orientation-sourced status, rollup and trace shape, and check findings with and without fix (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_orientation_tools.py`.
- [x] `P03.S18` - Add WorkspaceFactory tests for plan_progress, plan_edit, and the resolver: checked/unchecked batch marking, step add/insert/edit/remove identifier preservation, and the ambiguous-feature resolution error (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_plan_tools.py`.

### Phase `P04` - discover/invoke gateway

Build the stateless gateway: a catalog module parsing the vaultspec:generated markers in the CLI reference with the static denylist, the discover ranking tool over that catalog, and the invoke subprocess executor that runs the installed binary as a validated argv list.

- [x] `P04.S19` - Add the catalog module: parse the command inventory between the vaultspec:generated markers in the CLI reference at server start into an in-memory structure of verb paths, descriptions, and parameter schemas, applying the static denylist (uninstall, MCP registry mutation, index hand-authoring) at parse time (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/catalog.py`.
- [x] `P04.S20` - Add the discover tool: rank the parsed catalog over a query across verb paths and descriptions and return the ranked verb paths with their full parameter schemas, loaded into context only on demand, annotated read-only and idempotent (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools/gateway.py`.
- [x] `P04.S21` - Add the invoke tool: validate the verb path and argument object against the parsed inventory and denylist, build an argv list (never a shell), inject --target from the resolved root_dir, pass --json where the verb supports it, run the installed vaultspec-core binary with a timeout, fold stderr into the error payload, and return parsed JSON or captured stdout, annotated destructive (agent: vaultspec-high-executor); `src/vaultspec_core/mcp_server/tools/gateway.py`.
- [ ] `P04.S22` - Add WorkspaceFactory tests for the catalog: marker parsing yields the expected verb paths and schemas, and denylisted verbs are absent from both discover results and invoke acceptance (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_catalog.py`.
- [ ] `P04.S23` - Add tests for the gateway executor against the real uv run --no-sync vaultspec-core binary, covering a read-only verb returning parsed JSON, an unknown verb path rejected before spawn, a nonzero exit folding stderr into the error payload, and the discover ranking order (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_gateway.py`.

### Phase `P05` - cross-cutting closeout

Migrate whole-call failures to protocol isError, declare outputSchema/structuredContent and corrected annotations on all nine tools, confirm the isolation wrapper and server instructions string, audit the hot-verb help strings that become the discover payload, and add the nine-tool integration test plus code review.

- [ ] `P05.S24` - Migrate whole-call failures across every tool handler from the success-dict idiom to protocol isError, raising through FastMCP for invalid arguments, unknown verbs, and unresolvable targets while keeping per-item status only inside batch result arrays (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools`.
- [ ] `P05.S25` - Declare outputSchema and return structuredContent via FastMCP return-type derivation on all nine tools, replacing loose dict returns with typed result models (agent: vaultspec-standard-executor); `src/vaultspec_core/mcp_server/tools`.
- [ ] `P05.S26` - Correct the ToolAnnotations per ADR Q6: fix create's wrong idempotent hint to non-idempotent, mark edit and plan_edit and invoke destructive, keep plan_progress idempotent with explicit checked/unchecked only, and set status/find/discover read-only idempotent (agent: vaultspec-low-executor); `src/vaultspec_core/mcp_server/tools`.
- [ ] `P05.S27` - Wrap every new handler in \_isolated_context and extend the server instructions string to name the nine-tool surface and the tool-schema version, registering all tools through the updated register_tools bootstrap (agent: vaultspec-low-executor); `src/vaultspec_core/mcp_server/app.py`.
- [ ] `P05.S28` - Audit and tighten the hot-verb help strings in the CLI reference so the discover payload reads well verbatim, regenerating the inventory between the vaultspec:generated markers (agent: vaultspec-low-executor); `.vaultspec/reference/cli.md`.
- [ ] `P05.S29` - Add the nine-tool integration test asserting registration of all nine tools, outputSchema presence, corrected annotations, and isError on a whole-call failure (agent: vaultspec-standard-executor); `tests/unit/mcp_server/test_tool_surface.py`.
- [ ] `P05.S30` - Review the full nine-tool surface for ADR and reference fidelity: owning-verb routing, isError and envelope contract, annotations, and the subprocess injection guard (agent: vaultspec-code-reviewer); `src/vaultspec_core/mcp_server`.

## Parallelization

Phase P01 is a hard blocker for every later Phase: it publishes the shared edit-engine and the kebab-case normalizer that P02 and P03 import, so nothing in P02 through P05 may begin until P01 lands. All five Phases share one worktree, so cross-Phase parallelism is bounded by import dependencies rather than by process isolation.

Within P01, S01 precedes S02 (the renderers import the engine) and S03 precedes S04 (cmd_add imports the normalizer); the S01 and S03 tracks are mutually independent, and S05 follows once both land. After P01, P02 and P03 both build on the shared cores and touch mostly distinct modules, but the two edit the same `mcp_server/tools/documents.py` file (P02 adds create and edit, P03 extends find), so they sequence on that file rather than run truly in parallel; the plan-domain and orientation-domain steps of P03 (`plan.py`, `orientation.py`, `plan_resolver.py`) are genuinely independent of P02 and of each other. Within P03, S11 (the resolver) precedes S15 and S16, which consume it. P04 is independent of P02 and P03 once P01 lands (new files `catalog.py` and `tools/gateway.py`); S19 precedes S20 and S21. P05 is a strict closeout: it touches every tool module and depends on all prior Phases, so it runs last and its steps sequence against one another on the shared `tools` package. Every implementation step pairs with its WorkspaceFactory test before the Phase is considered done.

## Verification

The plan is complete when every Step is closed (`- [x]`). Each Phase carries a verifiable gate:

- P01: the new `vaultcore.edit_engine` and `vaultcore.normalize` modules exist with no Typer or console imports; `cmd_set_body`, `cmd_set_frontmatter`, and `cmd_edit` are thin renderers over `execute_edit`; the pre-existing set-body, set-frontmatter, and edit CLI tests pass unchanged; the new edit-engine and normalizer unit tests pass.
- P02: `create` contains no inline hydrate, filename, or atomic_write path and routes through `create_vault_doc` plus `generate_feature_index`; the `edit` tool enforces `expected_blob_hash` and returns the post-write `blob_hash`; batch partial-failure and intra-batch sequencing tests pass with zero mocks.
- P03: `find` returns `resource_link` and per-document `blob_hash` and sources status from orientation; `status`, `check`, `plan_progress`, and `plan_edit` are thin wrappers over their cores; the resolver raises on an ambiguous feature; all P03 tests pass.
- P04: the catalog parses the `vaultspec:generated` markers and enforces the denylist at both `discover` and `invoke`; the executor runs the real binary as an argv list with `--target` injected and `--json` where supported; the gateway tests pass, including the unknown-verb rejection and stderr-capture paths.
- P05: all nine tools declare `outputSchema`, return `structuredContent`, carry the corrected annotations, and are wrapped in `_isolated_context`; whole-call failures surface as `isError`; the server instructions string names the surface and version; the nine-tool integration test passes and code review signs off.

Whole-suite gate: `pytest src/vaultspec_core -m unit` passes, `vaultspec-core vault check all --feature mcp-tool-schema` is clean, and the vaultspec-code-reviewer audit of P05.S30 records no unresolved findings. For tier-specific verification cadence, see the authorizing documents in the `related:` frontmatter.
