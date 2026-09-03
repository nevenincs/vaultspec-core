# Vaultspec framework manual

This manual covers operating the vaultspec workflow in a project that is already set up.
For what vaultspec-core is and how to install it, see the [README](../README.md).

Two directories matter. `.vault/` holds the documents your features produce, and
`.vaultspec/` holds the framework policy: the rules, skills, and agent definitions your
coding agent reads. Commit both. The managed block in `.gitignore` excludes only the
per-machine by-products underneath them, such as `.vault/data/` and `.vault/logs/`, so
your teammates get the documents and the policy but not your local state. That block is
written into a `.gitignore` the project already has; the install does not create the
file, so a project started from an empty directory has nothing ignored until you create
one and install again. `vaultspec-core doctor` reports `gitignore info no_file` when
that is the case.

## How a feature flows into the vault

You begin a pipeline with one request, and the framework drives five stages plus an
optional code-grounding step. A skill runs each stage and writes a document to
`.vault/`:

| Stage                       | Skill                      | Writes to           |
| --------------------------- | -------------------------- | ------------------- |
| Research                    | `/vaultspec-research`      | `.vault/research/`  |
| Ground in code *(optional)* | `/vaultspec-code-research` | `.vault/reference/` |
| Decide                      | `/vaultspec-adr`           | `.vault/adr/`       |
| Plan                        | `/vaultspec-write`         | `.vault/plan/`      |
| Execute                     | `/vaultspec-execute`       | `.vault/exec/`      |
| Review                      | `/vaultspec-code-review`   | `.vault/audit/`     |

Those `/vaultspec-*` names are slash-commands you type into your coding agent, not into
a shell.

The agent runs the stages. Your part is approving each one before it moves on, and
stepping in where judgment is needed: shaping the decision, sizing the plan, and
deciding when work is done.

## Orient: see what is in flight

Run this first in any project you do not have fresh in your head, including your own
after a week away.

```text
$ vaultspec-core status
Vault Status

Plans in flight  (at least one open step)
  2026-06-26-search-api-plan   L2   -   P1/3   4/12 steps   33%   next P02.S05   2026-06-26

Recent changes
  research
    2026-06-26-search-api-research  2026-06-26
  adr
    2026-06-26-search-api-adr  2026-06-26

Active features
  search-api  3 docs plan  L2 4/12 33%  2026-06-26
```

A plan row reads left to right as: the plan's name, its tier, wave progress, phase
progress, step progress, percent complete, the next open step, and the date it last
changed. A bare `-` means that level does not exist at this tier, so the `L2` plan above
has phases but no waves. A completed run also appears under a `Recently completed`
heading, which this example omits.

Pass a feature or a plan as the target to get its grounding trace: every step mapped to
the execution record that carried it out, with the feature's other documents grouped
underneath.

```text
$ vaultspec-core status search-api
Grounding Trace  search-api (feature)

2026-06-26-search-api-plan   L2   -   P1/3   4/12 steps   33%   next P02.S05
    [x] P01.S01  2026-06-26-search-api-P01-S01
    [x] P01.S02  2026-06-26-search-api-P01-S02
  > [ ] P02.S05  no record
  grounding
    adr  2026-06-26-search-api-adr
    research  2026-06-26-search-api-research
```

`no record` means the step is open and nothing has been executed against it yet. The `>`
marks where work resumes.

## Begin a pipeline

Tell your coding agent what to build, in plain language:

> "Begin a vaultspec pipeline to implement full-text search for the API."

To enter at one stage instead, invoke its skill directly, for example
`/vaultspec-research`.

The agent pauses between stages and asks before continuing. Approving is a plain reply.
To redirect, say what is wrong and it revises that stage's document rather than moving
on, so a rejected research note gets rewritten before any decision is built on it.

## Find a feature's documents

List a feature's records, optionally by type:

```text
$ vaultspec-core vault list --feature search-api
Vault documents
  2026-06-26-search-api-research research #search-api 2026-06-26
  2026-06-26-search-api-adr adr #search-api 2026-06-26
  2026-06-26-search-api-plan plan #search-api 2026-06-26
```

When you do not know the name, search by meaning instead. That needs
[vaultspec-rag](https://github.com/nevenincs/vaultspec-rag), a separate package which is
not installed with vaultspec-core:

```bash
vaultspec-rag search "full-text ranking and tokenizer" --type vault
```

## Find and amend an ADR

A decision lives in an Architecture Decision Record (ADR). Find it by feature:

```bash
vaultspec-core vault list adr --feature search-api
```

You can amend one two ways. Ask the agent to revise the decision, and if the direction
changes it supersedes the old ADR rather than overwriting it. Or edit the ADR's body
prose yourself, then reconcile its frontmatter and links:

```bash
vaultspec-core vault check all --fix
```

A plan is built on its ADR, so changing a decision can invalidate work already planned
against it. After amending, run `vaultspec-core status <feature>` to see which plan
steps are still open, and revise the plan before executing further.

## Make a plan

From an approved ADR, `/vaultspec-write` produces the plan in `.vault/plan/`:

> "Write the implementation plan from the ADR."

A plan's tier sets how much structure it carries. `L1` is a single-session fix, steps
only. `L2` is multi-step work in one subsystem, grouping steps under phases. `L3` adds
waves above phases for interdependent batches. `L4` adds an epic frame for multi-week,
multi-team work. Ask for the tier you want, or let the skill choose from the scope and
change it later:

```bash
vaultspec-core vault plan tier promote .vault/plan/2026-06-26-search-api-plan.md --target L3
```

Each step names one unit of work and the file it touches, so it maps to a single commit:

```markdown
### Phase `P01` - rewrite the search index
- [ ] `P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `P01.S02` - replace inline scoring with the new ranker; `src/search/ranker.py`.
```

## Change a plan safely

Structural changes go through `vaultspec-core vault plan`, not your editor, which is
what keeps the `S##`, `P##`, and `W##` identifiers append-only: a removed step's
identifier is retired and never reused, so an execution record can never come to point
at different work than it did when written.

```bash
vaultspec-core vault plan step add     # append a step at the next canonical id
vaultspec-core vault plan step insert  # place one relative to an existing step
vaultspec-core vault plan step move    # re-parent or re-order
vaultspec-core vault plan step remove  # retire an identifier
vaultspec-core vault plan phase        # the same operations on phases
```

The full surface, including waves and epics, is in the [CLI reference](./CLI.md).

## Execute a plan

`/vaultspec-execute` works the plan from its next open step, writing one execution
record per step into `.vault/exec/`. That record is what makes a step's completion
auditable: it names what was changed, so `status` can later pair every closed step with
evidence.

To resume interrupted work, ask the agent to continue, or point it at a specific step.
`vaultspec-core status <feature>` names the next open step, which is the same one it
will pick up.

Mark step state yourself when you need to correct the record:

```bash
vaultspec-core vault plan step check    # mark closed
vaultspec-core vault plan step uncheck  # reopen
vaultspec-core vault plan step toggle   # flip
```

Reopen a step rather than deleting its record when work turns out to be incomplete. The
retired-identifier rule means a reopened step keeps its history.

## Review the result

`/vaultspec-code-review` audits finished work and writes the result to `.vault/audit/`,
ranked by severity. Run it when a plan's steps are closed and before you call the
feature done. What it finds either gets fixed, which may reopen steps, or gets recorded
as accepted. [The correctness workflow](./correctness.md) covers what the review gate
does and does not prove.

## Everyday commands

Check before you commit, and after an install or upgrade:

```bash
vaultspec-core vault check all --fix   # validate and repair the vault
vaultspec-core doctor                  # workspace and vault health together
```

`--fix` applies the repairs that are safe to make automatically. Anything it leaves
behind needs a decision: a dangling link means either the target should exist or the
link should go, and the tool will not guess. Re-run the check to confirm the finding is
gone. [Verifying a workspace and a vault](./verification.md) covers what each check
proves and which conditions change the exit code.

`vaultspec-core doctor` runs the workspace diagnosis and the vault checks under one exit
code. `vaultspec-core spec doctor` runs the workspace half alone, reporting the
framework, providers, builtins, `.gitignore`, and configuration.

To draw a feature's document graph as a tree grouped by feature and type:

```bash
vaultspec-core vault graph --feature search-api
```

The CLI maintains each document's `date:` and `modified:` stamps and the `body_hash:`
fingerprint that records what the body said when it was last stamped. Never hand-edit
them. If a check reports that a body changed without a stamp, run
`vaultspec-core vault check all --fix` to restamp it.

## Customize the policy

Edit resources under `.vaultspec/` through `vaultspec-core spec`, which is the command
group that addresses the policy tree, then sync them out to each provider. A provider is
a coding-agent integration such as Claude, Codex, or Gemini:

```bash
vaultspec-core spec rules add my-project-conventions
vaultspec-core sync    # writes .claude/, .gemini/, .codex/, and the shared .agents/
```

Commit `.vaultspec/` so a teammate inherits the policy on clone.
`vaultspec-core install --upgrade` carries an older workspace onto the current policy
after you upgrade the package.

To remove the framework from a project, `vaultspec-core uninstall` reverses the install.

## Decisions you make once

**Install mode.** Tool mode is the default and needs no action: hooks and the MCP server
run vaultspec-core through `uvx`, so it never enters your project's dependency set. If
your `pyproject.toml` lists vaultspec-core you are in dependency mode, which runs them
through `uv run`; dev mode is the same but keeps vaultspec-core out of your built
distributions. Pin one with `vaultspec-core install --mode <tool|dependency|dev>`. The
choice is recorded in a committed `workspace.json` so it travels with the project. The
[CLI reference](./CLI.md) has the details.

**Pre-commit hooks.** Not every project wants one. A tree-wide hook that rewrites the
working tree to the staged state will discard uncommitted changes outside the stage,
which is unsafe when several workers share one checkout, and some teams prefer to run
their gates explicitly. Of the four hooks written here, one mutates -
`vault sanitize annotations`, which strips generated template annotations - and the
other three only read; none is scoped to the files you staged. `vaultspec-core spec precommit disable` records that in the same
`workspace.json`, so no later `install` or `sync` regenerates `.pre-commit-config.yaml`.
`vaultspec-core spec precommit enable` reverses it.

**MCP clients.** `install` scaffolds an `.mcp.json` exposing the workflow to Model
Context Protocol clients over stdio: nine tools, plus a gateway to the rest of the CLI.
Verify the configuration with `vaultspec-core spec mcps status --json`; the
[MCP reference](./MCP.md) lists the tools.

## Machine-global runtime state

`~/.vaultspec/` is a per-account directory shared by vaultspec tools across every
repository on the machine. It is separate from a repository's `.vaultspec/`, which holds
that project's policy. You do not manage it by hand:

```text
~/.vaultspec/
├── mcp-ownership.json
└── procs/
    └── leases/
```

`procs/` holds process records and lease markers that coordinate concurrent sessions. A
record is stale when the process id it names is no longer alive.
`vaultspec-core spec doctor` reports the registry without changing it: an absent
`procs/` is informational, a live process id is healthy, and a dead one produces a
warning naming the stale record. The command never repairs or removes records. Reclaim a
stale record only through the tool that wrote it, and attach
`vaultspec-core spec doctor --json` when reporting a problem.

Tools that write into this namespace own their own record schemas, heartbeats, and
cleanup; vaultspec-core owns only the paths and the staleness rule, and its sync, prune,
and uninstall operations never rewrite the namespace. If you are building such a tool,
resolve the paths through `vaultspec_core.core.core_home_layout()` rather than spelling
them out, write records atomically, claim leases with an exclusive-creation primitive,
and keep credentials out of them.

## Related documentation

| Document                                               | What it covers                                      |
| ------------------------------------------------------ | --------------------------------------------------- |
| [Repository README](../README.md)                      | What vaultspec-core is, and installing it           |
| [A feature end to end](./examples.md)                  | One feature through the whole pipeline, with output |
| [Document syntax](./syntax.md)                         | Frontmatter, tags, links, and the plan row grammar  |
| [Verifying a workspace and a vault](./verification.md) | The health commands and what each check proves      |
| [The correctness workflow](./correctness.md)           | How a change is proven right, and the review gate   |
| [CLI reference](./CLI.md)                              | Every command, flag, and option                     |
| [MCP reference](./MCP.md)                              | The MCP server tools, setup, and configuration      |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/nevenincs/vaultspec-core/issues).
