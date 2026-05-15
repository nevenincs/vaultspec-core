# Vaultspec framework manual

Vaultspec is a governed development framework for artificial intelligence (AI)-assisted engineering. For installation and project overview, read the [repository README](../README.md).

Use this manual to develop features from initial research through to shipped code. Every step produces a durable record in `.vault/`. Use those records to make decisions once and build on them.

## How to start a new feature

Starting a feature means working through a structured sequence: research, decide, plan, execute, and review. You approve each phase before the next begins.

### Research

Ask your AI tool to research the problem space. Describe what you're trying to build and what you need to understand before committing to an approach.

> "Research authentication options for the API gateway - compare JWT, session tokens, and OAuth2"

The `vaultspec-research` skill explores trade-offs and documents options. It writes structured findings to `.vault/research/`. Review the output, correct any gaps, and approve it when the problem space is well understood.

For complex features, run multiple research rounds. Each round produces its own record, and later stages reference all of them.

### Grounding research in code

If you need to ground research in an existing codebase, invoke the `vaultspec-code-research` skill. Use it to understand how a system works, find reference implementations, or audit existing patterns.

> "How does the notification service currently handle delivery retries? Show me the retry logic and backoff strategy."

This produces a `.vault/reference/` record with code-grounded analysis: actual snippets, architectural observations, and patterns extracted from the codebase. These reference records feed directly into the next phase alongside your research.

You don't always need code research. For greenfield features or well-understood domains, general research may be enough. For features that touch existing systems, code research prevents decisions based on unsupported assumptions about the existing system.

### Architectural decisions

Once you've gathered enough context, formalize it into concrete architectural decisions using the `vaultspec-adr` skill. An architecture decision record (ADR) draws on the research findings and captures binding decisions about the approach.

> "Create an ADR recommending PostgreSQL full-text search for the REST API based on the research findings"

The ADR lands in `.vault/adr/`. It captures the context, the decision, its consequences, and links back to the research and reference records that informed it. ADRs are binding. They define the boundaries, library dependencies, and shape of the feature. The plan that follows must conform to what the ADR specifies.

Review the ADR carefully. This is where you commit to an approach. Sign off before moving to planning.

### Planning

With approved ADRs in hand, call the `vaultspec-write-plan` skill to produce an implementation plan. It reads the ADR and creates one checkbox row for each Step. The plan is grouped by the convention's complexity tier.

> "Write an implementation plan for the search feature based on the ADR"

Plans use the four-level hierarchy `Epic > Wave > Phase > Step`. Each plan declares its complexity tier in frontmatter as `tier: L1`, `L2`, `L3`, or `L4`. The tier determines which structural containers exist:

- `L1` (single session, single concern) emits Steps only.
- `L2` (cohesive multi-Step work in one package or subsystem) groups Steps under Phases.
- `L3` (hard interdependencies between batches) wraps Phases in Waves.
- `L4` (multi-week, multi-team) adds an Epic frame and an external project-management association.

`Step` is the canonical leaf-row noun at every tier. Each Step is one Markdown bulleted checkbox row pairing one prompt-run with one commit. Identifiers (`S##`, `P##`, `W##`) are flat, append-only, and immutable across plan revisions. The compound dot-notation (`W01.P02.S03`) is a display path computed from the current grouping, not the canonical ID.

Worked example (L2 plan, one Phase, three Steps):

```markdown
### Phase `P01` - rewrite the search index

One sentence stating what this Phase delivers.

- [ ] `P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `P01.S02` - replace inline scoring with the new ranker; `src/search/ranker.py`.
- [ ] `P01.S03` - update the index-rebuild command; `src/cli/reindex.py`.
```

Worked example (L3 plan, one Wave fragment showing Phase nesting):

```markdown
## Wave `W01` - foundational rewrite

Lands the new search-index API; `W02` depends on this Wave.

### Phase `W01.P01` - rewrite the search index
- [ ] `W01.P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `W01.P01.S02` - replace inline scoring; `src/search/ranker.py`.
```

The plan lands in `.vault/plan/`. It defines what gets built, in what order, and with what acceptance criteria. Review the scope. Confirm the tier matches the work's actual complexity, every Step is one row, and nothing overreaches the ADR's boundaries. Approve before execution begins.

Once the plan exists, every structural change goes through the `vaultspec-core vault plan` command-line interface (CLI) rather than the editor.

The CLI keeps canonical identifiers append-only and gap-no-reuse. When you remove a Step, its `S##` is retired permanently and recorded in a hidden ledger. The next Step gets the next available number, never the retired one. Hand-editing a checkbox or display path bypasses these guarantees, and `vaultspec-core vault plan check` flags it.

A typical flow has these operations:

1. Close a row with `vaultspec-core vault plan step check <plan> S07`, write the matching Step record, then commit.
1. Add a row at the tail of a Phase with `vaultspec-core vault plan step add <plan> --action "draft the connector module" --scope src/lib/connector.py --phase P02`.
1. Move a Step to a different Phase with `vaultspec-core vault plan step move <plan> S05 --to-phase P03 --before S08`.
1. Promote a plan with `vaultspec-core vault plan tier promote <plan> --target L3` when complexity grows.

The read-only views are:

- `vaultspec-core vault plan status` reports completion percent and tier.
- `vaultspec-core vault plan query` filters Step rows by container scope and open or closed state.
- `vaultspec-core vault plan check` validates the plan against the seven detection rules in the convention ADR.

Run `vaultspec-core vault plan check --fix` before commit to apply autofixable transformations idempotently. The full subcommand surface is documented in the [CLI reference](./CLI.md). The contract behind it is the CLI ADR (`2026-05-06-plan-hardening-adr`).

### Execution

Once the plan is approved, choose direct execution or parallel sub-agents.

**Direct execution.** Call the `vaultspec-execute` skill to work through the plan step by step. The AI delegates to specialized agent personas defined in the framework, each with a specific role and tool access level. Step records land in `.vault/exec/`.

> "Execute the search implementation plan"

**Parallel sub-agents.** When a plan has independent Steps, execution can dispatch multiple agents simultaneously using the agent definitions bundled with the framework.

Regardless of execution mode, code review is mandatory after completing a step or the full plan.

### Review and auditing

After execution, invoke the `vaultspec-code-review` skill to audit the completed work for safety, intent, and quality.

> "Review the changes from the search implementation"

The review produces a `.vault/audit/` record with issues triaged by severity: `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`. Critical and high-severity issues must be resolved before the feature closes. A clean review means the work is ready to ship.

For ongoing vault maintenance - fixing broken links, validating frontmatter, stripping generated template annotations, and cleaning up stale references - use the `vaultspec-curate` skill.

> "Audit the vault for broken links and missing references"

Run `vaultspec-core vault sanitize annotations` when you want to remove the
agent-facing template guidance from generated `.vault/` documents without
running the full repair pipeline.

## Customizing the framework

Edit resources under `.vaultspec/rules/` to customize the framework. The `vaultspec-core spec` command group manages these resources without requiring you to touch files directly:

```bash
# Add a custom rule
vaultspec-core spec rules add --name my-project-conventions

# Add a skill with a description
vaultspec-core spec skills add --name my-deploy --description "Deploy to staging"

# List what you have
vaultspec-core spec rules list
vaultspec-core spec skills list
vaultspec-core spec agents list
```

After any change, sync pushes generated provider resources into provider-specific destinations such as `.claude/`, `.gemini/`, shared `.agents/`, and `.codex/`:

```bash
vaultspec-core sync              # all installed providers
vaultspec-core sync claude       # one provider
vaultspec-core sync --dry-run    # preview without writing
```

See the [CLI reference](./CLI.md#spec-commands) for the full `vaultspec-core spec` command surface.

## Managing vault records

The `vaultspec-core vault` command group manages documents in `.vault/`. It creates documents from templates, lists records, validates links, and visualizes dependencies. See the [CLI reference](./CLI.md#vault-commands) for all commands and options.

## Model Context Protocol integration

The Model Context Protocol (MCP) server is an alternative integration path for MCP-capable clients like Claude Code. It exposes vault discovery and document creation over stdio transport without requiring file-based sync.

`vaultspec-core install` scaffolds an `.mcp.json` that invokes the server with `uv run python -m vaultspec_core.mcp_server.app`. Module invocation avoids binary locking on Windows. See the [MCP reference](./MCP.md) for setup and tool documentation.

## Related documentation

| Document                          | What it covers                                        |
| --------------------------------- | ----------------------------------------------------- |
| [Repository README](../README.md) | Project overview, installation, and getting started   |
| [CLI reference](./CLI.md)         | All commands, flags, and options for `vaultspec-core` |
| [MCP reference](./MCP.md)         | MCP server tools, setup, and configuration            |

For bug reports and feature requests, open an issue on the [vaultspec-core issue tracker](https://github.com/wgergely/vaultspec-core/issues).
