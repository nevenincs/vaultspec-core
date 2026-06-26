# Vaultspec framework manual

This manual is your working guide to developing a feature with vaultspec, from first
idea to shipped, reviewed code. Every stage leaves a durable record in `.vault/`, so the
work stays grounded in agreed intent. Nothing is lost between sessions or across team
members.

This manual assumes vaultspec is already installed and provisioned in your project -
provisioned means you have run `vaultspec-core install`. If you haven't set up a project
yet, start with the [repository README](../README.md) for installation and an overview.

## How the pieces fit (read this first)

Vaultspec is a spec-driven harness for coding agents. You drive a coding agent - Claude
Code, Codex, or Gemini - and it invokes vaultspec skills, which are slash-commands such
as `/vaultspec-research`. Those skills call the `vaultspec-core` command-line tool
(CLI), which reads and writes the durable records on your behalf.

Two directories define the framework. `.vault/` holds every document your features
produce: research findings, decisions, plans, execution records, and audits.
`.vaultspec/` holds the framework policy - rules, skills, agent personas, and system
prompts - that shapes how the coding agent behaves in your project.

You write down and approve research, decisions, and plans before any code is written.
Every coding agent - even one working in an isolated sandbox - then builds toward the
same agreed goal. The records in `.vault/` carry that agreement forward across sessions,
agents, and contributors.

## Orientation - the zeroth move

Before you start work in a project you have no session context for, run
`vaultspec-core status`. Orientation is the zeroth move: read-only, no artifact, no
pipeline phase. It describes what exists.

With no argument, `vaultspec-core status` shows a vault-wide rollup. You see every plan
with open steps and its completion percentage, recently modified documents grouped by
type, and the features in flight.

Pass a `TARGET` - a plan stem, a file path, or a feature tag - and the output shifts
from rollup to grounding trace. Each plan step appears mapped to its execution-record
stem. The grounding documents for that feature - research, reference, and audit files -
are nested under each step. This is how you trace a plan forward through its steps and
records, and backward through the documents that grounded the decisions behind it.

Orientation describes what exists; it does not score the vault against its structural
rules. When you want that, use `vaultspec-core vault check`, covered under
[Managing vault records](#managing-vault-records).

## Developing a feature, stage by stage

A feature moves through five stages - research, decide, plan, execute, and review - and
you approve each before the next begins. This is the same pipeline the README names;
here is how to run it. To keep it concrete, the rest of this section follows one running
example: adding full-text search to an API. Map it onto your own feature as you go.

### Research

Start by asking your coding agent to explore the problem in natural language. Give it
enough context to compare real options:

> "Research options for adding full-text search to the API - compare PostgreSQL
> full-text search, a dedicated search service, and an embedded index."

The `vaultspec-research` skill explores trade-offs and documents options, writing
structured findings to `.vault/research/`. Review the output, correct gaps, and approve
when the problem space is well understood. For complex features, run multiple rounds.
Each round produces its own record that later stages reference.

### Grounding research in code

If you need to ground research in an existing codebase, invoke the
`vaultspec-code-research` skill before moving to decisions:

> "How does the API currently store and query the records we want to search? Show me the
> data-access layer."

It produces a `.vault/reference/` record with real snippets, architectural observations,
and patterns from the codebase. You don't always need it - greenfield or well-understood
domains may not - but for features touching existing systems it prevents decisions built
on unsupported assumptions.

### Architectural decisions

Once you've gathered enough context, formalize it into an Architecture Decision Record
(ADR) with the `vaultspec-adr` skill:

> "Create an ADR recommending PostgreSQL full-text search for the API based on the
> research findings."

The ADR lands in `.vault/adr/`, capturing the context, the decision, its consequences,
and links back to the research and reference records that informed it. ADRs are binding:
they define the boundaries, dependencies, and shape that the plan must conform to.
Review carefully and sign off before planning.

### Planning

With approved ADRs in hand, call the `vaultspec-write` skill to produce an
implementation plan in `.vault/plan/`.

> "Write an implementation plan for the search feature based on the ADR."

The skill scaffolds a plan document organized around the `Epic > Wave > Phase > Step`
hierarchy. The `tier` key in frontmatter (`L1` through `L4`) controls which structural
containers the plan uses. `L1` covers a single session, single concern - Steps only.
`L2` groups Steps under Phases for cohesive multi-step work in one subsystem. `L3` wraps
Phases in Waves for interdependent batches across multiple sessions. `L4` adds an Epic
frame for multi-week, multi-team work and requires an external project-management
association. At every tier, `Step` is the leaf row - one checkbox pairing one prompt-run
with one commit. The full tier table and identifier rules live in the
[CLI reference](./CLI.md).

A plan fragment for the search feature might look like this:

```markdown
### Phase `P01` - rewrite the search index
- [ ] `P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `P01.S02` - replace inline scoring with the new ranker; `src/search/ranker.py`.
```

### Working the plan with the vault plan CLI

Once a plan exists, make every structural change through `vaultspec-core vault plan`
rather than the editor. The CLI keeps canonical identifiers (`S##`, `P##`, `W##`)
append-only. Removing a Step retires its number permanently. The next Step gets the next
available number, never a reused one. Hand-editing a checkbox or display path bypasses
these guarantees, and `vaultspec-core vault plan check` flags it.

A few representative operations:

```bash
# Mark a step complete
vaultspec-core vault plan step check <plan> S07

# Add a step to a phase
vaultspec-core vault plan step add <plan> --action "draft the connector module" --scope src/lib/connector.py --phase P02

# Promote the plan's complexity tier
vaultspec-core vault plan tier promote <plan> --target L3
```

Read-only views round out the surface: `vault plan status` reports completion and tier,
`vault plan query` filters Step rows, and `vault plan check` validates the document. Run
`--fix` before commit to apply autofixes. The full subcommand surface is in the
[CLI reference](./CLI.md).

### Execution

Once the plan is approved, choose between direct execution and parallel sub-agents.

For direct execution, call the `vaultspec-execute` skill to work the plan step by step.
The skill delegates to agent personas defined in the framework. Each persona carries a
specific role and tool-access level - some write files and run commands, others only
read and report. Step records land in `.vault/exec/`.

> "Execute the search implementation plan."

When a plan has independent Steps, dispatch multiple agents at once using the agent
personas bundled with the framework. Either way, code review is mandatory after
completing a step or the full plan.

### Review and auditing

After execution, invoke the `vaultspec-code-review` skill to audit the completed work
for safety, intent, and quality.

> "Review the changes from the search implementation."

The review produces a `.vault/audit/` record with issues triaged by severity:
`critical`, `high`, `medium`, and `low`. Resolve all `critical` and `high` issues before
the feature closes. A clean review means the feature is ready to ship.

For ongoing vault upkeep - broken links, frontmatter, and stale references - use the
`vaultspec-curate` skill. Run `vaultspec-core vault sanitize annotations` to strip
generated template guidance from documents. Use `--dry-run` to preview first.

## Extending and operating the framework

With the feature workflow in hand, these sections cover the operating concerns -
customizing the framework, sharing it across a team, maintaining the vault, and
integrating over the Model Context Protocol.

### Customizing the framework

Edit resources under `.vaultspec/rules/` through the `vaultspec-core spec` command group
rather than touching files directly.

```bash
vaultspec-core spec rules add my-project-conventions
vaultspec-core spec skills add my-deploy --description "Deploy to staging"

vaultspec-core spec rules list
vaultspec-core spec skills list
vaultspec-core spec agents list
```

After any change, run `sync` to push generated provider resources into their
destinations - `.claude/` for Claude Code, `.gemini/` for Gemini, `.agents/` for the
shared agents surface, and `.codex/` for Codex.

```bash
vaultspec-core sync                  # all installed providers
vaultspec-core sync claude           # one provider
vaultspec-core sync --dry-run        # preview changes without writing
```

The full flag and subcommand surface is in the [CLI reference](./CLI.md).

### Sharing policy

The spec layer is team-shared by default. A teammate who clones the project inherits its
authoritative policy immediately. Codifying a rule is durable work - it reaches every
teammate on their next clone and every continuous integration (CI) run, without
requiring a separate communication step.

Authored content under `.vaultspec/` - rules, skills, agents, and system prompts -
belongs in git alongside the synthesized `CLAUDE.md`, `.mcp.json`, and the generated
provider directories. Only genuine per-machine runtime by-products stay local. The
`install` and `sync` commands write a managed block to `.gitignore`, delimited by
`# >>> vaultspec-managed (do not edit this block) >>>` markers. The block ignores the
snapshot directory, lock sentinels, the install manifest at `.vaultspec/providers.json`,
and the vault's local caches.

To carry an older workspace onto the shared policy, run
`vaultspec-core install --upgrade`. It rewrites a stale managed block in place while
leaving any block you have hand-edited untouched.

### Managing vault records

The `vaultspec-core vault` command group is the authoritative surface for vault
documents. It creates documents from templates, lists and filters records, validates
links and frontmatter, and visualizes the dependency graph between documents. The
`vault check` command you use during orientation and the `vault sanitize annotations`
command you run during review are both part of this group. See the
[CLI reference](./CLI.md) for the full subcommand surface.

One frontmatter detail worth knowing: `date:` records when a document was created, and
`modified:` records when it last changed. The CLI maintains `modified:` automatically -
mutating verbs and `vaultspec-core vault check all --fix` update it on your behalf.
Never hand-edit `modified:`.

### Model Context Protocol integration

The Model Context Protocol (MCP) server is an alternative integration path for
MCP-capable clients like Claude Code. It exposes vault discovery and document creation
over stdio, with no file-based sync. Clients interact with the vault through tool calls
instead of reading generated files.

`vaultspec-core install` scaffolds an `.mcp.json` that invokes the server with:

```bash
uv run python -m vaultspec_core.mcp_server.app
```

Module invocation avoids binary locking on Windows, where a compiled entry point held
open by one process blocks updates from another.

Verify configuration health at any time:

```bash
vaultspec-core spec mcps status --json
```

See the [MCP reference](./MCP.md) for setup steps and tool documentation.

## Related documentation

| Document                          | What it covers                                      |
| --------------------------------- | --------------------------------------------------- |
| [Repository README](../README.md) | Project overview, installation, and getting started |
| [CLI reference](./CLI.md)         | Every command, flag, and option for vaultspec-core  |
| [MCP reference](./MCP.md)         | The MCP server tools, setup, and configuration      |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/nevenincs/vaultspec-core/issues).
