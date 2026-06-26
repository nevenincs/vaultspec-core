# Vaultspec framework manual

This manual covers developing a feature with vaultspec, from idea to shipped, reviewed
code. Every stage leaves a durable record in `.vault/`, so intent survives across
sessions, agents, and teammates. It assumes vaultspec is already installed and
provisioned (you have run `vaultspec-core install`); if not, start with the
[README](../README.md).

## How the pieces fit (read this first)

Vaultspec is a spec-driven harness for coding agents. You drive a coding agent (Claude
Code, Codex, Gemini); it invokes vaultspec skills (slash-commands like
`/vaultspec-research`), which call the `vaultspec-core` CLI to read and write the
records.

Two directories define it. `.vault/` holds the documents your features produce -
research, decisions, plans, execution records, audits. `.vaultspec/` holds the policy -
rules, skills, agent personas, system prompts - that shapes how the agent behaves.

You write down and approve the research, decision, and plan before any code, so every
agent - even one in an isolated sandbox - builds toward the same goal.

## Orientation - the zeroth move

In a project you have no context for, run `vaultspec-core status` first. This zeroth
move is read-only and describes what exists; it produces no artifact and belongs to no
phase.

With no argument it shows a vault-wide rollup: every plan with open steps and its
completion percentage, recently modified documents by type, and the features in flight.

Pass a `TARGET` (plan stem, path, or feature tag) and it becomes a grounding trace -
each plan step mapped to its execution record, with the feature's research, reference,
and audit documents nested underneath. This traces a plan forward to its records and
back to the decisions behind it.

Orientation describes; it does not score. For that, use `vaultspec-core vault check`,
covered under [Managing vault records](#managing-vault-records).

## Developing a feature, stage by stage

A feature moves through five stages - research, decide, plan, execute, review - and you
approve each before the next. Here is how to run them, followed through one example:
adding full-text search to an API.

### Research

Ask your coding agent to explore the problem in natural language, with enough context to
compare real options:

> "Research options for adding full-text search to the API - compare PostgreSQL
> full-text search, a dedicated search service, and an embedded index."

The `vaultspec-research` skill weighs trade-offs and writes structured findings to
`.vault/research/`. Review, correct gaps, and approve. Complex features take several
rounds, each its own record that later stages reference.

### Grounding research in code

To ground research in existing code, invoke `vaultspec-code-research` before deciding:

> "How does the API currently store and query the records we want to search? Show me the
> data-access layer."

It writes a `.vault/reference/` record of real snippets, patterns, and observations from
the codebase. Greenfield work may skip it, but for features touching existing systems it
stops decisions built on guesswork.

### Architectural decisions

With enough context, formalize the decision into an Architecture Decision Record (ADR)
via `vaultspec-adr`:

> "Create an ADR recommending PostgreSQL full-text search for the API based on the
> research findings."

The ADR lands in `.vault/adr/`, capturing the context, decision, and consequences,
linked back to the research that informed it. ADRs are binding - they set the boundaries
the plan must obey - so review and sign off before planning.

### Planning

From an approved ADR, `vaultspec-write` produces an implementation plan in
`.vault/plan/`:

> "Write an implementation plan for the search feature based on the ADR."

Plans use an `Epic > Wave > Phase > Step` hierarchy, and the frontmatter `tier` (`L1`
through `L4`) sets which containers exist: `L1` Steps only; `L2` Steps under Phases;
`L3` Phases under Waves; `L4` an Epic frame for multi-week, multi-team work. A `Step` is
the leaf row at every tier - one checkbox pairing one prompt-run with one commit. The
full tier table and identifier rules are in the [CLI reference](./CLI.md).

A fragment for the search feature:

```markdown
### Phase `P01` - rewrite the search index
- [ ] `P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `P01.S02` - replace inline scoring with the new ranker; `src/search/ranker.py`.
```

### Working the plan with the vault plan CLI

Make every structural change through `vaultspec-core vault plan`, not the editor. It
keeps identifiers (`S##`, `P##`, `W##`) append-only: a removed Step's number retires for
good, never reused. Hand-editing a checkbox or display path bypasses that guarantee, and
`vault plan check` flags it.

Representative operations:

```bash
# Mark a step complete
vaultspec-core vault plan step check <plan> S07

# Add a step to a phase
vaultspec-core vault plan step add <plan> --action "draft the connector module" --scope src/lib/connector.py --phase P02

# Promote the plan's complexity tier
vaultspec-core vault plan tier promote <plan> --target L3
```

Read-only views: `vault plan status` (completion and tier), `vault plan query` (filter
Steps), `vault plan check` (validate; `--fix` autofixes before commit). Full surface in
the [CLI reference](./CLI.md).

### Execution

With the plan approved, run it directly or in parallel. `vaultspec-execute` works the
plan step by step, delegating to agent personas - each with a role and tool-access
level, some writing files, some read-only. Step records land in `.vault/exec/`.

> "Execute the search implementation plan."

Independent Steps can run as several agents at once. Either way, code review is
mandatory afterward.

### Review and auditing

After execution, `vaultspec-code-review` audits the work for safety, intent, and
quality:

> "Review the changes from the search implementation."

It writes a `.vault/audit/` record with issues by severity (`critical`, `high`,
`medium`, `low`); resolve every `critical` and `high` before closing. A clean review
ships.

For ongoing upkeep - broken links, frontmatter, stale references - use
`vaultspec-curate`. `vaultspec-core vault sanitize annotations` strips generated
template guidance (`--dry-run` to preview).

## Extending and operating the framework

The remaining sections cover operating concerns: customizing, sharing, maintaining the
vault, and MCP integration.

### Customizing the framework

Edit resources under `.vaultspec/rules/` through `vaultspec-core spec`, not by hand:

```bash
vaultspec-core spec rules add my-project-conventions
vaultspec-core spec skills add my-deploy --description "Deploy to staging"

vaultspec-core spec rules list
vaultspec-core spec skills list
vaultspec-core spec agents list
```

After any change, `sync` pushes generated resources to each provider - `.claude/`,
`.gemini/`, the shared `.agents/`, and `.codex/`:

```bash
vaultspec-core sync                  # all installed providers
vaultspec-core sync claude           # one provider
vaultspec-core sync --dry-run        # preview changes without writing
```

Full surface in the [CLI reference](./CLI.md).

### Sharing policy

The spec layer is team-shared by default: anyone who clones the project inherits its
policy, so codifying a rule reaches every teammate and every continuous integration (CI)
run.

Authored content - `.vaultspec/` rules, skills, agents, and system prompts, plus the
synthesized `CLAUDE.md`, `.mcp.json`, and generated provider directories - belongs in
git. Only per-machine by-products stay local: `install` and `sync` write a managed
`.gitignore` block (marked `# >>> vaultspec-managed (do not edit this block) >>>`) that
ignores the snapshot directory, lock sentinels, the install manifest
(`.vaultspec/providers.json`), and the vault's caches.

`vaultspec-core install --upgrade` carries an older workspace onto this policy,
rewriting a stale managed block while leaving a hand-edited one untouched.

### Managing vault records

The `vaultspec-core vault` group is the authoritative surface for vault documents: it
creates them from templates, lists and filters records, validates links and frontmatter,
and graphs dependencies. `vault check` (orientation) and `vault sanitize annotations`
(review) both belong to it. Full surface in the [CLI reference](./CLI.md).

One frontmatter detail: `date:` is creation, `modified:` is last change. The CLI
maintains `modified:` automatically (mutating verbs and `vault check all --fix` update
it); never hand-edit it.

### Model Context Protocol integration

The Model Context Protocol (MCP) server is an alternative to file-based sync for clients
like Claude Code: it exposes vault discovery and document creation over stdio, so
clients work through tool calls instead of reading files.

`vaultspec-core install` scaffolds an `.mcp.json` that invokes the server with:

```bash
uv run python -m vaultspec_core.mcp_server.app
```

Module invocation (`python -m`) avoids the Windows binary lock that a console-script
entry point would hold.

Verify configuration health at any time:

```bash
vaultspec-core spec mcps status --json
```

See the [MCP reference](./MCP.md) for setup and tool documentation.

## Related documentation

| Document                          | What it covers                                      |
| --------------------------------- | --------------------------------------------------- |
| [Repository README](../README.md) | Project overview, installation, and getting started |
| [CLI reference](./CLI.md)         | Every command, flag, and option for vaultspec-core  |
| [MCP reference](./MCP.md)         | The MCP server tools, setup, and configuration      |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/nevenincs/vaultspec-core/issues).
