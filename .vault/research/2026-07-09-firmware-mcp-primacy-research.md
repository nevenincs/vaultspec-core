---
tags:
  - '#research'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
related: []
---

# `firmware-mcp-primacy` research: rewording the firmware from CLI-mandating to MCP-first

## Scope and framing

This grounds a Fable-authored ADR that will decide how far, and by what wording pattern, to shift the vaultspec-core firmware (the builtins under `src/vaultspec_core/builtins/`) from mandating CLI invocation toward naming the verified MCP server as the primary tool. The firmware is the always-preloaded context that every managed session carries: the always-on rules, the assembled system prompt, and the ten dispatched agent personas. A nine-tool MCP server now exists and is verified end-to-end over stdio (`src/vaultspec_core/mcp_server/`), so the question is whether preloading `uv run --no-sync vaultspec-core ...` invocation syntax is still the right context spend. The hard constraint is that the firmware installs into projects where the MCP may not be connected, and the ten personas run as dispatched subagents whose declared tool allowlists contain no MCP tool at all. The stance is Fable's to set; what follows is the grounding.

A note on one input claim: the motivating "CLI miss rate" figure cited during scoping (a 7.9% headline) does not appear in the committed `cli-usage-analytics` vault documents; that audit concerns the analytics module's implementation, not a headline miss rate. The `cli-usage-analytics` feature is the right provenance for the "CLI calls are miss-prone and context-heavy" motivation, but the exact percentage is from the analytics tool's own generated output (gitignored), not a quotable vault finding. Fable should treat the motivation as sound and the precise number as unverified-in-vault.

## Front 1 - The current firmware surface and its CLI mandate

The firmware splits into three always-preloaded classes plus one read-on-demand lookup. The rules and system files are assembled into every provider's context; the personas load when dispatched; `reference/cli.md` is explicitly not assembled into any provider config and is loaded only when an agent reads it (and, separately, parsed by the MCP gateway - see Front 4).

### Always-on rules (`src/vaultspec_core/builtins/rules/`)

| File                                   | Approx size | CLI-mandate strength                       | What is transport-prescriptive                                                                                                                                                                                                                                                                                                                                                                |
| :------------------------------------- | :---------- | :----------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rules/vaultspec-cli.builtin.md`       | ~117 lines  | Highest. The entire file is a CLI mandate. | Nearly all of it: the `## Mandate` ("Use `vaultspec-core` to create, read, audit, and repair"), a full `## Commands` command catalog enumerating ~20 `vaultspec-core ...` invocations, and a `## Runtime` block that literally prescribes `uv run --no-sync vaultspec-core <cmd>` and `--target`/`--dry-run`/`--json`/`--force` flags. This is the file most saturated with transport syntax. |
| `rules/vaultspec.builtin.md`           | ~289 lines  | Low-to-medium, mostly capability-worded.   | Largest file, but overwhelmingly framework concepts (tag taxonomy, doc hierarchy, placeholder conventions). Transport-prescriptive touches are narrow: line 22 names `vaultspec-core vault plan` as the plan authority, and lines 105/247 name `vaultspec-core vault feature index` as index owner. The bulk is intent/convention, not invocation.                                            |
| `rules/vaultspec-discovery.builtin.md` | ~33 lines   | Medium, but already dual-worded.           | Leads with `vaultspec-rag search ...` and `vaultspec-core status/vault list/vault graph` as concrete commands, then closes (line 31-32) with the graceful-degradation clause: "Where `vaultspec-rag` is not installed, the `vaultspec-core` discovery verbs and grep carry the same sequence." This is the existing template for fallback wording.                                            |

### Assembled system prompt (`src/vaultspec_core/builtins/system/`)

| File                      | Approx size | CLI-mandate strength                                 | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| :------------------------ | :---------- | :--------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `system/01-core.md`       | ~61 lines   | None transport-specific.                             | Generic engineering mandates. Line 8 already says "using the available tools, skills, and MCPs" - MCP is named as a first-class surface here. No `vaultspec-core` invocations.                                                                                                                                                                                                                                                                     |
| `system/02-operations.md` | ~101 lines  | None vaultspec-transport-specific.                   | Output efficiency, tone, `git`/pre-commit workflow. Its "CLI Interaction" heading is about the agent's own tone, not vaultspec commands.                                                                                                                                                                                                                                                                                                           |
| `system/03-vaultspec.md`  | ~104 lines  | Medium; capability-worded with pointed CLI mandates. | The pipeline table and skill routing are intent-worded. Transport-prescriptive spots: line 16 (`vaultspec-core vault feature index`), lines 18-19 ("run `vaultspec-core status`"), and the strongest, lines 54-60: "The `vaultspec-core vault plan` CLI is the canonical surface ... Writers and executors MUST use the `vaultspec-core vault plan ...` CLI verbs ... rather than hand-editing." That MUST is the system-prompt-level CLI mandate. |
| `system/90-custom.md`     | ~6 lines    | None.                                                | Empty custom-rules placeholder.                                                                                                                                                                                                                                                                                                                                                                                                                    |

### The ten agent personas (`src/vaultspec_core/builtins/agents/`)

All ten declare a `mode:` and an explicit `tools:` allowlist. The CLI footprint concentrates in the write-capable pipeline personas:

| Persona                            | mode       | `tools:` allowlist                              | CLI-mandate weight                                                                                                                                                                                                                              |
| :--------------------------------- | :--------- | :---------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vaultspec-writer.md`              | read-write | `[Glob, Grep, Read, Write, Edit, Bash]`         | Highest. A dedicated `## CLI usage mandate` section enumerating `vaultspec-core vault plan step add/insert/move/remove`, `phase`, `wave`, `epic intent edit`, `tier promote/demote`.                                                            |
| `vaultspec-standard-executor.md`   | read-write | `[Glob, Grep, Read, Write, Edit, Bash]`         | High. `Scaffold` bullet mandates `vaultspec-core vault add exec --feature ... --step ... --related ...`; `CLI usage mandate` bullet mandates `vaultspec-core vault plan step check/uncheck/toggle` and forbids hand-editing the checkbox glyph. |
| `vaultspec-low-executor.md`        | read-write | `[Glob, Grep, Read, Write, Edit, Bash]`         | High. Same `vault add exec` + `vault plan step check/uncheck/toggle` mandate as standard-executor.                                                                                                                                              |
| `vaultspec-high-executor.md`       | read-write | `[Glob, Grep, Read, Write, Edit, Bash]`         | High. Same executor mandate pattern.                                                                                                                                                                                                            |
| `vaultspec-docs-curator.md`        | read-write | `[Glob, Grep, Read, Write, Edit, Bash]`         | Medium (7 `vaultspec-core` references).                                                                                                                                                                                                         |
| `vaultspec-adr-researcher.md`      | read-only  | `[Glob, Grep, Read, WebFetch, WebSearch, Bash]` | Low-medium (discovery-worded; `vaultspec-rag`/`vaultspec-core` discovery verbs).                                                                                                                                                                |
| `vaultspec-researcher.md`          | read-only  | `[Glob, Grep, Read, WebFetch, WebSearch, Bash]` | Low. Discovery method only; no vaultspec mutation commands.                                                                                                                                                                                     |
| `vaultspec-reference-auditor.md`   | read-only  | `[Glob, Grep, Read, Bash]`                      | Low (1 reference).                                                                                                                                                                                                                              |
| `vaultspec-code-reviewer.md`       | read-only  | `[Glob, Grep, Read, Bash]`                      | Low (2 references).                                                                                                                                                                                                                             |
| `vaultspec-project-coordinator.md` | read-write | `[Glob, Grep, Read, Bash]`                      | Low (1 reference).                                                                                                                                                                                                                              |

The decisive structural fact for Front 3: not one persona lists an MCP tool in its `tools:` allowlist. Every persona that touches vaultspec state reaches it through `Bash` running `vaultspec-core`. The personas are, by their own frontmatter, CLI-bound today regardless of what the top-level rules say.

### The MCP registration (`src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json`)

Four lines: `{"command": "uv", "args": ["run", "python", "-m", "vaultspec_core.mcp_server.app"]}`. This is the source definition that `mcp_sync` merges into `.mcp.json` (Front 4). It is the only firmware surface that registers the server; it does not itself instruct any agent.

### `reference/cli.md` - dual role

`src/vaultspec_core/builtins/reference/cli.md` is large (a full command inventory) but its own header states: "This file is a reference document, not a rule. It is not assembled into any provider configuration." So it is not standing context; it is a read-on-demand lookup. Critically, it also carries the machine-generated `vaultspec:generated:begin command-inventory` marker block that the MCP `discover`/`invoke` gateway parses as its authoritative verb catalog (`src/vaultspec_core/mcp_server/catalog.py`). This dual role is the byte-stability coupling detailed in Front 4.

## Front 2 - The MCP surface now available (the replacement primary)

The server (`src/vaultspec_core/mcp_server/app.py`, `_build_instructions`) exposes seven first-class "hot path" tools plus a two-tool gateway to the long tail. Mapping each firmware CLI mandate to its MCP equivalent:

| Firmware CLI mandate (source)                                                                | MCP tool                                                                  | First-class? |
| :------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------ | :----------- |
| `vaultspec-core status` (cli rule, `03-vaultspec.md`)                                        | `status` (`tools/orientation.py`, wraps `compute_rollup`/`compute_trace`) | Yes          |
| `vaultspec-core vault list` / `vault feature list` (cli rule)                                | `find` (`tools/documents.py`, doc-search + feature-listing superset)      | Yes          |
| `vaultspec-core vault add <type> --feature ...` (writer/executor personas)                   | `create` (batch, `tools/documents.py`, routes through `create_vault_doc`) | Yes          |
| body-prose edits after scaffold (executor personas)                                          | `edit` (batch, blob-hash optimistic concurrency, `execute_edit`)          | Yes          |
| `vaultspec-core vault plan step check/uncheck/toggle` (executor personas, `03-vaultspec.md`) | `plan_progress` (`tools/plan.py`)                                         | Yes          |
| `vaultspec-core vault plan step add/insert/edit/remove` (writer persona)                     | `plan_edit` (`tools/plan.py`)                                             | Yes          |
| `vaultspec-core vault check all [--fix]` (cli rule)                                          | `check` (`tools/orientation.py`, wraps `run_all_checks`)                  | Yes          |
| everything else (~115 long-tail verbs)                                                       | `discover` then `invoke` (`tools/gateway.py`)                             | Gateway only |

The gateway is a validated subprocess boundary: `invoke` runs the installed binary as an argv list with `--target` injected and `--json` appended where supported (`tools/gateway.py`, `_build_argv`). So even long-tail firmware mandates remain reachable through MCP, just not first-class.

### Firmware-mandated operations with NO first-class tool, or none at all

- `vaultspec-core sync` and `spec <resource> sync` (cli rule maintenance section): reachable only via `discover`/`invoke`, not a hot tool.
- `vaultspec-core vault feature index` (mandated in `vaultspec.builtin.md` and `03-vaultspec.md`): explicitly denylisted from the gateway (`catalog.py` `DENYLIST`: index hand-authoring stays uncreatable/uneditable via MCP). It is reachable neither as a hot tool nor via `invoke`. The MCP handles index regeneration as a side effect of `create` instead, so the firmware's explicit "run `vaultspec-core vault feature index`" instruction has no MCP verb behind it.
- `vaultspec-core spec mcps add/remove/sync` (part of the `spec` surface the cli rule names): denylisted, owned by the `spec mcps` lifecycle, not the tool surface. Read-only `spec mcps list`/`status` are intentionally not denied.
- `vaultspec-core uninstall`: denylisted.
- `vaultspec-core vault plan tier promote/demote`, `epic intent edit`, `phase`/`wave` verbs (writer persona mandate): no first-class tool; reachable via `invoke` only. `plan_edit` covers step-level structural edits but not tier/epic/wave-level manipulation.

This asymmetry matters for Fable: the writer persona's structural-plan vocabulary (`tier promote`, `wave add`, `epic intent`) and the maintenance verbs (`sync`, `feature index`) are precisely the operations that do not have hot-tool equivalents, so any wording that claims "the MCP replaces the CLI" would be incorrect for exactly those mandates.

## Front 3 - Availability and subagent access (the core constraint)

This is the reason the firmware cannot go MCP-only.

### Can a session detect whether the MCP is connected?

There is a workspace-configuration signal but not a live-connection signal. `mcp_status()` in `src/vaultspec_core/core/mcps.py` reports whether the source definition under `.vaultspec/mcps/` is represented in the workspace `.mcp.json`, and whether managed entries have drifted. It returns statuses like `ok`, `partial`, `missing_config`, `no_definitions`, `no_context`. But this reports registration-on-disk, not whether the host actually loaded the server and exposed its tools to the current agent. An agent reads this only by running `vaultspec-core spec mcps status --json` (itself a CLI call, a bootstrapping circularity if the premise is "prefer MCP"). There is no firmware-level runtime probe an agent can consult to branch its behavior. The honest conclusion: the firmware cannot reliably self-detect MCP availability at authoring time and must degrade gracefully by wording, not by conditional logic. The existing `vaultspec-discovery.builtin.md` fallback clause is the proven pattern for this.

### Do dispatched subagents inherit the parent's MCP tools?

This is the load-bearing distinction, and the firmware's own frontmatter answers most of it without needing external harness docs:

Every one of the ten personas declares an explicit `tools:` allowlist (Front 1 table), and no persona lists any MCP tool - the allowlists are exclusively harness-native (`Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch`). Each write-capable persona reaches vaultspec through `Bash` running `vaultspec-core`. So independent of whatever the host harness does with MCP inheritance, the personas as currently authored are structurally CLI-bound: a persona restricted to `[Glob, Grep, Read, Write, Edit, Bash]` cannot call `create` or `plan_edit` even if those tools were present in the dispatching session, because its allowlist excludes them.

On the harness question proper (does the Claude Code Task tool, or equivalent, propagate MCP tools into a subagent) the firmware itself carries no evidence and I found none in the vault or codebase. `03-vaultspec.md` describes personas as "Parallel sub-agents" dispatched "through the host environment" and stresses that `mode:` is declared intent, not a sandbox. That framing implies the host controls the tool surface, and the persona's `tools:` list is the declared subset. The prudent reading, well-supported by the allowlists, is that agent personas should be treated as NOT having MCP tools unless a persona is explicitly reworded and re-scoped to include them. Fable should hold this as high-confidence for the current personas (their allowlists prove it) and as explicit uncertainty for the general harness-inheritance mechanism (no firmware evidence either way).

### What "MCP-first with CLI fallback" wording looks like without doubling every instruction

The proven pattern already lives in `vaultspec-discovery.builtin.md`: state the capability and the primary tool once, then a single trailing fallback clause. Applied to this domain, capability-worded instructions ("use vaultspec-core to scaffold the execution record for this Step; the `create` tool is the primary path, or the `vaultspec-core vault add exec` CLI where the MCP is not connected") are correct in both worlds because they name the intent, name the MCP tool as primary, and preserve the CLI as the named fallback, without enumerating full `uv run --no-sync ...` invocation syntax inline. The distinction Fable must hold: top-level rules and the system prompt can safely go MCP-first-with-fallback because they address the orchestrating session (which may have MCP); the ten personas address subagents (which, per their allowlists, do not) and so should stay CLI-capable via `Bash` even if their wording foregrounds capability over transport.

## Front 4 - Sync mechanics and blast radius

### How builtins propagate

Rules, skills, agents, and the system prompt sync from `.vaultspec/...` sources into generated provider directories via `sync_files`/`sync_to_all_tools` (`src/vaultspec_core/core/sync.py`). MCP definitions take a different path: `mcp_sync` (`core/mcps.py`) merges every `.vaultspec/mcps/*.json` into the shared workspace `.mcp.json` plus each installed provider's native MCP config, tracking ownership under the `_vaultspecManaged` sidecar key so user-added servers are never clobbered. `reference/cli.md` is generated into `builtins/reference/cli.md` by `spec reference generate` (`src/vaultspec_core/cli/reference_gen.py`) and installed to `.vaultspec/reference/cli.md`; it is not assembled into any provider config.

### Blast radius

Rewording any always-on rule, system file, or persona changes the `.vaultspec/` source, and every managed project that runs `vaultspec-core sync` (or the next `install`) re-propagates the change into its provider directories. The blast radius is therefore every managed project on the next sync: this is a firmware-wide edit, the widest-reaching class of change the framework ships. The `.claude/rules/*.builtin.md` files at this repo's own root are themselves synced copies, so the change is dogfooded here first.

### Byte-stability coupling (the sharp edge)

`reference/cli.md` is not just a lookup; its `vaultspec:generated:begin command-inventory` marker block is the sole verb-existence source for the MCP gateway. `catalog.py` (`_parse_inventory`) parses that block into the `CommandCatalog`; the module states the block "is the authoritative verb-existence source per the accepted ADR (Q7)" and that its absence is raised loudly rather than silently yielding an empty catalog. The consequence for Fable: the marker block is generator-owned and must stay in exact sync with the installed Typer command tree (a drift test, `test_cli_reference_drift`, enforces this). If the ADR proposes trimming `reference/cli.md`, only the human-facing prose outside the markers is safe to touch; editing anything inside the markers, or removing the block, breaks the MCP `discover`/`invoke` gateway. The prose header and the generated inventory serve different masters (agent lookup vs gateway catalog) and must be reasoned about separately.

### Migration concerns

`reference/cli.md`'s marker block regenerates via `spec reference generate` and is drift-tested, so no schema migration is needed for content that stays generator-owned. A firmware reword is a content change to `.vaultspec/` sources, propagated by ordinary `sync`, not a `migrations`-class change. Fable should nonetheless consider versioning: the MCP server already stamps a tool-schema version (the package version, per the tool-schema ADR, surfaced in `_build_instructions`). A reworded firmware that assumes a given MCP tool surface is implicitly coupled to that server version; a project on an older server but a newer firmware, or vice versa, is a skew case worth naming.

## Open design questions for Fable

1. How far to push MCP primacy. Three postures: (a) MCP-first-with-CLI-fallback (name the MCP tool as primary, keep a single fallback clause), (b) MCP-only-assumed (drop CLI syntax, assume the server is connected - incorrect for un-connected installs and for the current personas), (c) minimal-mention (name capability/intent only, let the harness route to MCP or CLI). Given Front 3, (b) is unsafe firmware-wide; the real choice is between (a) and (c), possibly differing by surface.
1. Whether and how to detect MCP availability. There is no live-connection probe (Front 3); `spec mcps status` reports registration-on-disk and is itself a CLI call. Decide whether the firmware attempts any detection at all or relies purely on graceful-degradation wording (the `vaultspec-discovery` fallback pattern).
1. Whether the ten agent personas go MCP-first or stay CLI. Their `tools:` allowlists contain no MCP tool, so they are CLI-bound today. Decide whether to (a) leave personas CLI-worded, (b) reword personas to capability/intent while keeping `Bash`+CLI as the mechanism, or (c) re-scope persona `tools:` allowlists to include MCP tools - which only helps if subagents actually inherit the server, an open harness question.
1. The dual-world wording pattern. Settle the canonical sentence shape (capability + primary MCP tool + single CLI-fallback clause) that reads correctly whether or not the MCP is connected, without doubling every instruction. The `vaultspec-discovery.builtin.md` fallback clause is the existing template.
1. The fate of `reference/cli.md` and the CLI-reference rule. Decide whether `reference/cli.md` and the `## References` pointer in `vaultspec-cli.builtin.md` stay intact (they serve both the CLI fallback and, non-negotiably, the MCP gateway catalog) or get trimmed. Any trim must not touch the `vaultspec:generated` marker block, which the gateway parses and a drift test guards.
1. Which specific mandates have no first-class MCP tool. `sync`, `feature index` (denylisted), `spec mcps *` (denylisted), `uninstall` (denylisted), and the writer persona's `tier promote/demote`, `wave`, and `epic intent` verbs are gateway-only or unreachable via MCP (Front 2). Wording that implies "the MCP covers the CLI" is factually wrong for these; decide how the reworded firmware speaks about them.
1. Migration and versioning of the reworded firmware. A reword is a `sync`-propagated content change with firmware-wide blast radius, not a schema migration. Decide whether to gate any MCP-assuming wording on the tool-schema/package version the server stamps, to avoid firmware/server skew.
