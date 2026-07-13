---
tags:
  - '#research'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
related: []
---

# `mcp-tool-schema` research: grounding a progressive-discovery MCP tool surface for vaultspec-core

## Purpose and framing

This research arms a Fable-authored ADR that will (re)design the vaultspec-core MCP tool schema. The explicit design stance is that the schema is **not** a 1:1 port of the 124-verb CLI. The CLI is the exhaustive operator surface; the MCP surface is a curated, progressively-discoverable agent surface shaped by three forces: the current MCP protocol's discovery mechanics, the settled in-repo MCP architecture, and hard empirical usage data. All three are developed below, then distilled into design constraints and open questions for the ADR.

A single distinction governs everything downstream and Fable must internalize it first: **this repo runs the FastMCP that ships inside the official `mcp` SDK, not the standalone `fastmcp` 2.x/3.x package.** `pyproject.toml` declares `mcp>=1.26.0` and the server imports `from mcp.server.fastmcp import FastMCP` (`src/vaultspec_core/mcp_server/app.py`, `src/vaultspec_core/mcp_server/vault_tools.py`). There is no `fastmcp` dependency. The bleeding-edge progressive-discovery primitives (built-in Tool Search transform, `enable`/`disable`, `ToolTransform`) belong to the standalone package; the SDK-bundled FastMCP is a leaner FastMCP-1.x-equivalent. Whether to adopt those primitives is therefore a dependency decision, not a free capability - flagged as an open question below.

## Front 1 - Current MCP protocol state and progressive tool discovery (mid-2026)

### Spec revisions grounded

Two revisions bracket the current state. The **stable revision is `2025-06-18`** (the tool mechanics vaultspec targets today), and a **release candidate dated `2026-05-21` and shipping `2026-07-28`** is in flight. Fable should design against `2025-06-18` semantics as the floor and treat the RC as forward-looking risk to accommodate, not depend on.

What `2025-06-18` already gives the tool surface:

| Capability           | Field / message                                                                                                             | Relevance to vaultspec                                                                                                                   |
| :------------------- | :-------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| Pagination           | `tools/list` accepts `cursor`, returns `nextCursor`                                                                         | A large tool catalog can be paged, but paging does not reduce the model's context cost once loaded - it defers transport, not tokens.    |
| List-changed         | `tools` capability `listChanged: true`; `notifications/tools/list_changed`                                                  | The protocol foundation for **dynamic/lazy tool exposure**: a server may swap its advertised tool set mid-session and notify the client. |
| Annotations          | `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, plus `title`                                          | Behavior hints the host uses to decide confirmation prompts. Clients MUST treat them as untrusted unless the server is trusted.          |
| Structured output    | `outputSchema` on the tool; `structuredContent` on the result (with a serialized-JSON `TextContent` mirror for back-compat) | Lets tool results be validated, typed objects rather than prose blobs.                                                                   |
| Result content types | `text`, `image`, `audio`, `resource_link`, embedded `resource`                                                              | `resource_link` lets a tool return a pointer to a vault document instead of inlining its body.                                           |
| Errors               | protocol errors (`-32602` unknown tool / bad args) vs `isError: true` tool-execution errors                                 | The current `create` tool returns `{"success": false, ...}` dicts rather than `isError`; a schema redesign should reconcile this.        |

What the `2026-05-21` RC adds or moves: a **stateless protocol core** (no `initialize` handshake, no `Mcp-Session-Id`; call metadata in `_meta`); `tools/list` gains `ttlMs` and `cacheScope` freshness metadata; `inputSchema`/`outputSchema` widen to full **JSON Schema 2020-12** (`oneOf`/`anyOf`/`allOf`, conditionals, `$ref`) and `structuredContent` may be any JSON value; **elicitation** reshaped as `InputRequiredResult` + `inputResponses` retry rather than held-open streams; a **Tasks** extension (tool call returns a task handle driven by `tasks/get|update|cancel`); a first-class **Extensions** framework; and formal **deprecation of roots, sampling, and logging** (12-month window). The stateless direction and full-JSON-Schema input shapes are the two RC items most worth designing to be compatible with.

### The "too many tools floods the context" problem and its named answers

The core problem is quantified consistently across sources: a production agent in early 2026 connects to 5-20 MCP servers each exposing 5-50 tools, and "ten servers and twenty tools at 500 tokens each equals 100,000 tokens before the user has typed a word." Standard MCP degrades past roughly **50 tools**, because every tool's full JSON schema is serialized into the system prompt on every request, inflating cost and hallucination risk. Preloaded catalogs "broke down because tool surface scaled faster than context windows did." This is precisely vaultspec's problem: 124 CLI verbs cannot become 124 tools without drowning the host.

The modern answer is **progressive tool discovery / progressive tool loading**: defer the verbose body of a tool definition until the agent actually needs it. The agent still learns tools exist, but loads full schemas and parameter descriptions on demand. Concrete named patterns:

| Pattern                                                                 | Mechanism                                                                                                                                                                                                                                                         | Best for / tradeoff                                                                                                                                                                                                                                | Source     |
| :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------- |
| **Meta-tool / tool-search gateway**                                     | LLM initially sees only a `tool_search(query)` meta-tool; host runs BM25 or vector search over an external registry and **injects** matched schemas into the conversation just-in-time. Anthropic marks deferred schemas with a conceptual `defer_loading: true`. | Theoretically unlimited tools behind one visible tool; cost is an extra search round-trip and a search/execution duality in tool descriptions. This harness itself uses exactly this: deferred tools fetched on demand via a ToolSearch meta-tool. | atheo.dev  |
| **Strict Lazy**                                                         | Only a compact index stays in context (10-30 tokens/tool); full schemas load and unload per call.                                                                                                                                                                 | High tool counts, short tasks, cost-sensitive; more load/unload churn.                                                                                                                                                                             | Wire       |
| **Sticky Lazy**                                                         | Index plus schemas of any tool used this session.                                                                                                                                                                                                                 | Multi-step tasks with tool reuse; less aggressive savings.                                                                                                                                                                                         | Wire       |
| **Bounded Sticky (LRU)**                                                | Index plus the N most-recently-used schemas (typ. 5-10). Called out as the production default for general-purpose agents.                                                                                                                                         | Good balance; needs an eviction policy.                                                                                                                                                                                                            | Wire       |
| **Code-Mediated**                                                       | Index only; tools invoked from generated code in a sandbox. Reported ~98.7% token reduction (150k -> 2k) on a benchmark; Anthropic April-2026 reference.                                                                                                          | Largest savings; most invasive to deploy.                                                                                                                                                                                                          | Wire       |
| **Namespacing / grouping + filtering + server-side tool-set switching** | Group tools by domain, expose a subset, and swap sets via `listChanged`.                                                                                                                                                                                          | Simpler than a search gateway; coarser granularity.                                                                                                                                                                                                | tools spec |

Two cross-cutting observations Fable should weigh: progressive disclosure is now described as "the default in production MCP design," not a novel technique; and there is independent evidence that tool **descriptions themselves are frequently low-quality** and materially affect agent efficiency - meaning the promoted-tool descriptions vaultspec ships are load-bearing, not cosmetic.

### How FastMCP supports these (with the SDK caveat)

The standalone `fastmcp` package (gofastmcp.com) supports the full progressive toolkit: runtime `mcp.add_tool()`; server-level visibility control `mcp.disable(tags={...})` / `mcp.enable(tags={...}, only=True)` (v3.0.0+, replacing the deprecated per-tool `enabled`); tag-based grouping `@mcp.tool(tags={...})`; automatic `notifications/tools/list_changed` on add/remove/enable/disable (v2.9.1+); structured output from return-type annotations with `@mcp.tool(output_schema=...)` override (v2.10.0+); `ToolAnnotations` hints (v2.2.7+); and a `ToolTransform`/`ToolTransformConfig` transformation pipeline plus a **built-in Tool Search transform that "replaces large tool catalogs with on-demand search."**

The critical caveat: **vaultspec-core does not depend on that package.** It uses `mcp>=1.26.0`'s bundled FastMCP, which reliably provides `@mcp.tool` with `ToolAnnotations`, structured output via return types, `Context` logging, and the protocol-level `listChanged`/pagination primitives - but does **not** ship the 2.x/3.x `disable`/`enable`, `ToolTransform`, or built-in Tool Search transform. Any meta-tool / tool-search gateway on the current dependency must be **hand-rolled** on top of `@mcp.tool` and the low-level list-changed notification, or the project must add `fastmcp` as a dependency. This is the single largest feasibility fork in the ADR.

## Front 2 - The existing in-repo MCP surface and settled prior-ADR constraints

### What the server exposes today

The live surface is minimal and is the baseline being overhauled. `src/vaultspec_core/mcp_server/` contains exactly `app.py`, `vault_tools.py`, and `__init__.py`. `create_server()` builds one `FastMCP(name="vaultspec-mcp", ...)` and calls `register_vault_tools(mcp)`. That registers **two tools only**:

- **`find`** - read-only, idempotent (`ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)`). With no args it lists features with doc counts and `VaultGraph` weight rankings; with `feature`/`type`/`date` it searches documents. `type` defaults to `["adr", "plan", "research", "reference"]`, deliberately excluding exec and audit. Optional `body: bool` inlines full document text; optional `json: bool` enriches feature entries with inferred lifecycle status.
- **`create`** - write, non-destructive, idempotent. Scaffolds a vault document from a type template, validating kebab-case feature/title/tags, resolving `related` inputs to wiki-links, enforcing feature-lifecycle dependencies (exec requires plan+ADR, plan warns without ADR), rejecting `index` (auto-generated), and self-validating the written file. It returns `{"success": bool, "message": str, ...}` dicts, **not** MCP `isError` results.

Notable gaps against the CLI: there is no plan-structure manipulation (`vault plan step ...`), no `status`/orientation tool, no feature index, no `vault check`, no batch or edit operation. Handlers run inside a copied `contextvars.Context` via `_isolated_context` to prevent per-request state leaking across concurrent calls.

### Registration, install, and config story

The server ships as the `vaultspec-mcp` console script (`app.run()` -> Typer callback -> `_serve` -> `mcp.run()` over stdio). Registration into a project's `.mcp.json` is governed by the **`mcp-registry` ADR**: one JSON file per server under `.vaultspec/mcps/` (`{name}.builtin.json` bundled in the wheel, `{name}.json` for custom), whose stem becomes the `mcpServers` key. Confirmed on disk: `.vaultspec/mcps/vaultspec-core.builtin.json` runs `uv run python -m vaultspec_core.mcp_server.app`, and `.vaultspec/mcps/vaultspec-rag.builtin.json` runs `vaultspec-search-mcp`. The CLI surface is `vaultspec-core spec mcps {list,status,add,remove,sync}`, with `mcp_sync()` doing a key-level JSON merge that preserves user entries, and doctor detecting `REGISTRY_DRIFT`. The `--skip mcp` opt-out is preserved across install/sync/uninstall.

### Settled architecture the ADR must not contradict

- **`mcp-consolidation` ADR** (accepted): all MCP server code lives under `mcp_server/`; the name must **not** shadow the third-party `mcp` package (rules out an `mcp/` subpackage). It explicitly anticipated the current situation: "The unified `mcp_server/` package will eventually host ~35 tools... If client-side tool sprawl becomes a concern, tool namespacing or grouping can be introduced at the FastMCP registration layer without changing the package structure." The historical subagent/team tool modules it describes are **no longer present** - the surface was pared back to `find`/`create`, so the schema redesign is a clean expansion, not a re-consolidation.
- **`mcp-registry` ADR** (accepted): MCP definitions are workspace-scoped JSON, not provider-scoped; `.mcp.json` management is data-driven through the registry; the ADR must not add server runtime management (start/stop) - that is out of scope by prior decision.

Net: Fable is free to redesign the **tool schema** (names, shapes, discovery mechanics) but must keep the package under `mcp_server/`, keep registration flowing through the `spec mcps` / `.vaultspec/mcps/*.json` registry, and avoid re-introducing runtime server management.

## Front 3 - Empirical usage data as design constraints

From the completed `cli-usage-analytics` audit, treated as established data: 124 declared verb paths, ~19.9k invocations over 30 days across Claude and Codex, 69% surface coverage (38 verbs never invoked), 7.9% miss rate. Translated into tool-schema implications:

**Promote to first-class tools (the hot path).** These verbs dominate real usage and should be directly visible, not behind discovery:

| Hot verb                | ~30-day count | Tool-shape implication                                                                                                  |
| :---------------------- | :------------ | :---------------------------------------------------------------------------------------------------------------------- |
| `vault plan step check` | 3.5k          | A dedicated plan-progress tool (check/uncheck/toggle a step). Highest-frequency operation; ergonomics matter most here. |
| `vault add`             | 2.6k          | Already partially covered by `create`; dominant flag shape is `--feature`+`--related`.                                  |
| `vault plan status`     | 1.65k         | An orientation/status tool - currently absent from MCP entirely.                                                        |
| `vault plan step add`   | 1.5k          | A plan-authoring tool; dominant shape `--feature`+`--step` and `--action`+`--scope`.                                    |
| `vault feature index`   | 1.35k         | Index regeneration as a tool (or an implicit side-effect of create/check).                                              |
| `vault check all`       | 1.23k         | A validation/repair tool (`--fix`).                                                                                     |
| `status`                | high          | Top-level orientation - the agent's "where am I" - currently absent from MCP.                                           |

**Parameter shapes to bake in.** Flag co-occurrence tells the tool signatures: `--feature`+`--related` and `--feature`+`--step` and `--action`+`--scope` dominate. The `vault add` shape (feature + related + tags) and the `plan step add` shape (feature + step + action + scope) are the two canonical create/author signatures the schema should model directly, rather than exposing raw flag bags.

**Push behind progressive discovery or drop (the dead surface).** 38 of 124 verbs were never invoked in 30 days: nearly all `spec agents *` and `spec hooks *`, `config get/set/unset`, `vault check orphans/encoding`, `vault feature unarchive`, `vault link remove`, `plan phase move/renumber`, `plan wave insert/move`, `plan trailer validate`, `uninstall`. These are **omission or deep-discovery candidates** - either absent from the tool surface entirely or reachable only through a tool-search gateway, never occupying first-class schema slots.

**Fix the ergonomic gaps (the miss rate).** The 7.9% miss rate concentrates on the **hot** verbs (`step check`, `plan step add`, `vault add`) - bad flag guesses and retry-after-help. This is the strongest argument for structured, well-annotated, tightly-typed tool schemas on exactly the promoted tools: the tools agents use most are where they fail most, so schema precision (enums, required-field clarity, `outputSchema`, actionable error messages via `isError`) directly buys down the miss rate.

**Batch / edit / create shapes (user-requested).** The user wants edit, batch-edit, modify, create, and batch-create. Mapping onto tool shapes: the current `create` covers single-create only; there is **no edit tool at all** and no batch variant. Candidate shapes are a single `edit`/`modify` tool operating on body prose (respecting the "never hand-write frontmatter/filenames" rule - edits must go through owning verbs, not raw file writes), and batch variants that accept a list of create/edit operations in one call to amortize round-trips. Batch operations pair naturally with structured output (per-item success/failure arrays) and with the `create` tool's existing per-item `{"success": ...}` result idiom.

## Open design questions for the ADR

Fable must decide, at minimum:

1. **Flat vs tiered surface.** A single flat tool set (promote ~7-9 hot tools, drop the rest) vs a tiered progressive surface (a handful of first-class hot tools plus a `search_tools`/`load_tool` gateway fronting the long tail). Given 124 verbs and the ~50-tool degradation threshold, a purely flat full-coverage surface is off the table; the real choice is "curated flat" vs "curated flat + discovery gateway."
1. **Meta-tool gateway vs static grouping/filtering.** If progressive discovery is adopted, is it a hand-rolled `search_tools` meta-tool over a tool registry, or coarser tag-grouping + `listChanged` set-switching? This decision is gated by the FastMCP dependency choice below.
1. **Dependency fork: SDK-bundled FastMCP vs standalone `fastmcp`.** Adopt `fastmcp` 2.x/3.x to get built-in Tool Search / transforms / enable-disable, or stay on `mcp>=1.26.0` and hand-roll any dynamic exposure? This is the highest-leverage decision and interacts with the `mcp-consolidation` no-name-shadow constraint.
1. **Orientation as tools vs resources.** The user's must-haves - `status`, feature list, in-flight plans, plan grounding, pending steps - could be tools, MCP **resources** (read-only, addressable, `resource_link`-returnable), or a mix. Resources fit read-only orientation data well and keep the tool count down; tools fit action-triggering. Which orientation data is a tool vs a resource?
1. **Edit / modify / batch tool shapes.** What is the exact signature of `edit`/`modify` (body-prose only, or structured plan-step edits routed through `vault plan` verbs?), and do batch-create / batch-edit take operation lists returning structured per-item results? How does batch interact with the lifecycle-dependency validation the current `create` enforces?
1. **Annotations and structured output policy.** Which tools carry `readOnlyHint`/`destructiveHint`/`idempotentHint`, and do all promoted tools ship `outputSchema` + `structuredContent`? Should `create`/`edit` migrate from `{"success": false}` dicts to protocol `isError` results?
1. **Mapping the 124-verb declared surface to a discoverable catalog.** If a gateway exists, what is its backing catalog - the CLI reference (`.vaultspec/reference/cli.md`), a curated subset, or a generated index - and how is it kept in sync with the CLI so discovery never advertises a non-existent verb?
1. **Installation and versioning.** How the redesigned surface ships through the existing `.vaultspec/mcps/vaultspec-core.builtin.json` registry unchanged, and how tool-schema versions are signaled to hosts (server `instructions`, tool `title`s, or a version resource) given the impending stateless `2026-05-21` protocol core.

## Sources

- MCP Tools spec, revision 2025-06-18: `modelcontextprotocol.io/specification/2025-06-18/server/tools`
- MCP 2026-07-28 release candidate (dated 2026-05-21): `blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/`
- Wire, "Progressive tool loading is the new MCP context pattern": `usewire.io/blog/progressive-tool-loading-mcp-context-pattern/`
- Andreas van den Boogaard, "Progressive Tool Discovery and The Evolution of MCP": `atheo.dev/articles/Progressive-Tool-Discovery-&-The-Evolution-of-MCP`
- FastMCP tools reference: `gofastmcp.com/servers/tools`
- FastMCP tool transformation: `gofastmcp.com/patterns/tool-transformation`
- "MCP Tool Descriptions Are Smelly" (tool-description quality): `arxiv.org/html/2602.14878v1`
- In-repo: `src/vaultspec_core/mcp_server/app.py`, `src/vaultspec_core/mcp_server/vault_tools.py`, `src/vaultspec_core/mcp_server/__init__.py`, `src/vaultspec_core/cli/spec_cmd.py`, `.vaultspec/mcps/vaultspec-core.builtin.json`, `.vault/adr/2026-02-22-mcp-consolidation-adr.md`, `.vault/adr/2026-04-11-mcp-registry-adr.md`, `.vault/adr/2026-07-09-cli-usage-analytics-adr.md`
