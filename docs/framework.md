# Vaultspec framework manual

This manual covers operating the vaultspec workflow in a project that is already set up.
For what vaultspec is and how to install it, see the [README](../README.md). In one
line: `.vault/` holds the documents your features produce, and `.vaultspec/` holds the
framework policy.

## How a feature flows into the vault

You begin a pipeline with one request, and the framework drives five stages (plus an
optional code-grounding step). A skill runs each stage and persists a document to
`.vault/`, pausing for your approval before the next:

| Stage                       | Skill                      | Persists to         |
| --------------------------- | -------------------------- | ------------------- |
| Research                    | `/vaultspec-research`      | `.vault/research/`  |
| Ground in code *(optional)* | `/vaultspec-code-research` | `.vault/reference/` |
| Decide                      | `/vaultspec-adr`           | `.vault/adr/`       |
| Plan                        | `/vaultspec-write`         | `.vault/plan/`      |
| Execute                     | `/vaultspec-execute`       | `.vault/exec/`      |
| Review                      | `/vaultspec-code-review`   | `.vault/audit/`     |

The framework runs research, execute, and review; the rest of this manual covers where
you step in: orienting, finding documents, shaping the ADR and plan, and day-to-day
operation.

## Begin a pipeline

Tell your coding agent what to build, in plain language:

> "Begin a vaultspec pipeline to implement full-text search for the API."

To enter at one stage instead, invoke its skill directly, for example
`/vaultspec-research`.

## Orient: see what is in flight

Run `vaultspec-core status` to see where work stands. With no argument it prints a
vault-wide rollup:

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

Pass a feature (or plan) as the target for its grounding trace - every step mapped to
its execution record, with the feature's documents grouped underneath:

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

## Find a feature's documents

List a feature's records directly, optionally by type:

```text
$ vaultspec-core vault list --feature search-api
Vault documents
  2026-06-26-search-api-research research #search-api 2026-06-26
  2026-06-26-search-api-adr adr #search-api 2026-06-26
  2026-06-26-search-api-plan plan #search-api 2026-06-26
```

When you do not know the name, search by meaning:

```bash
vaultspec-rag search "full-text ranking and tokenizer" --type vault
```

## Find and amend an ADR

A decision lives in an Architecture Decision Record (ADR). Find it by feature:

```bash
vaultspec-core vault list adr --feature search-api
```

Amend it either way: ask the agent to revise the decision - it reopens the ADR and
supersedes it if the direction changes - or edit the ADR's body prose and reconcile its
frontmatter and links:

```bash
vaultspec-core vault check all --fix
```

ADRs are binding, so a change can ripple into the plan that depends on it.

## Make a plan and set its tier

From an approved ADR, `/vaultspec-write` produces the plan in `.vault/plan/`:

> "Write the implementation plan from the ADR."

A plan's tier sets its structure: **L1** for a single-session fix (Steps only), **L2**
for multi-step work in one subsystem (Steps under Phases), **L3** for interdependent
batches (Phases under Waves), and **L4** for multi-week, multi-team work (an Epic
frame). Ask for the tier you want, or let the skill choose from the scope and adjust
later:

```bash
vaultspec-core vault plan tier promote .vault/plan/2026-06-26-search-api-plan.md --target L3
```

Each Step pairs one file with one commit:

```markdown
### Phase `P01` - rewrite the search index
- [ ] `P01.S01` - extract the tokenizer; `src/search/tokenizer.py`.
- [ ] `P01.S02` - replace inline scoring with the new ranker; `src/search/ranker.py`.
```

Every structural change goes through `vaultspec-core vault plan` rather than the editor,
keeping identifiers (`S##`, `P##`, `W##`) append-only. The full surface is in the
[CLI reference](./CLI.md).

## Operate day to day

**Customize.** Edit resources under `.vaultspec/` through `vaultspec-core spec`, then
sync them to each provider (a coding-agent integration such as Claude, Codex, or
Gemini):

```bash
vaultspec-core spec rules add my-project-conventions
vaultspec-core sync                       # writes .claude/, .gemini/, .codex/, and the shared .agents/
```

**Share.** Commit `.vaultspec/` so a teammate inherits the policy on clone; the managed
`.gitignore` block keeps per-machine by-products local.
`vaultspec-core install --upgrade` carries an older workspace onto the shared policy.

**Choose an install mode.** Provisioning is mode-aware, with three modes. Tool mode, the
default, wires the pre-commit hooks and the MCP launch command to run vaultspec-core
through `uvx`, so a project adopts the framework without vaultspec-core ever entering
its own dependency set. Dependency mode runs them through `uv run` and is selected when
the project's `pyproject.toml` lists vaultspec-core. Dev mode is for vaultspec-core
placed in the default `dev` dependency group: it renders exactly like dependency mode
but does not ship in the project's built distributions, so choosing it records that
non-leaking placement as a distinct declared state. Pin any with
`vaultspec-core install --mode tool`, `vaultspec-core install --mode dependency`, or
`vaultspec-core install --mode dev`. The chosen mode is committed alongside
`.vaultspec/` in a per-package `workspace.json`, so it travels with the workspace and a
project running vaultspec-core beside a companion package can declare each in its own
mode; `vaultspec-core install --upgrade` records a mode for a workspace provisioned
before modes existed by inferring it from the existing hook and dependency shape.

**Or decline the hooks entirely.** Not every project wants a commit hook: a tree-wide
hook that rewrites the working tree to the staged state is unsafe when several workers
share one checkout, and some teams run their gates explicitly instead.
`vaultspec-core spec precommit disable` records that in the same committed
`workspace.json`, so no later `install` or `sync` regenerates `.pre-commit-config.yaml`
and the managed `.gitignore` block starts ignoring it.
`vaultspec-core spec precommit enable` reverses the decision.

**Maintain.** `vaultspec-core vault check all --fix` validates and repairs the vault,
and `vaultspec-core vault graph --feature search-api` visualizes a feature. The CLI
maintains each document's `date:` and `modified:` stamps, and the `body_hash:`
fingerprint that tells it when a document's prose changed without a stamp; never
hand-edit any of them.

**Connect MCP clients.** `install` scaffolds an `.mcp.json` exposing the workflow to
Model Context Protocol (MCP) clients over stdio: nine tools covering orientation,
discovery, scaffolding, prose edits, checks, and plan progress, plus a gateway to the
rest of the CLI. Verify the configuration with `vaultspec-core spec mcps status --json`;
see the [MCP reference](./MCP.md).

## Core home runtime artifacts

VaultSpec Core reserves `~/.vaultspec/` as the per-account, machine-global home
shared by VaultSpec tools. This directory is separate from a repository's
`.vaultspec/` directory. The repository directory contains workspace policy and
configuration. The home directory coordinates runtime state across repositories
and concurrent sessions.

The supported home layout includes:

```text
~/.vaultspec/
├── mcp-ownership.json
└── procs/
    ├── <producer-defined process records>.json
    └── leases/
        └── <producer-defined lease markers>
```

`procs/` and all of its nested paths are reserved runtime-artifact
namespaces. A process record describes a development process and identifies it
with a process ID (PID). A lease marker coordinates exclusive or shared access
to a machine resource. A record is stale when its positive integer `pid` names
a process that the operating system proves is no longer alive.

Core owns the paths and their preservation contract. The producer owns the
record and lease schemas, creation, atomic mutation, heartbeat policy, and
reclamation. Core owns only the narrow doctor rule that a proven-dead positive
integer PID makes a record stale. Core does not create `procs/` eagerly: a
producer creates the directory when it first writes runtime state. Core sync,
prune, and workspace uninstall operations do not rewrite or delete the
machine-global namespace. This contract applies on every platform supported by
VaultSpec Core.

Resolve the namespace through
`vaultspec_core.core.core_home_layout()` instead of spelling the path in a new
Core integration. Keep credentials and token values out of records. Use atomic
writes for records. Use exclusive creation or an equivalent race-safe primitive
for claims. The producer remains the authority for heartbeat, ownership,
cleanup, and schema evolution.

`vaultspec-core spec doctor` reports the registry without changing it:

- An absent `procs/` directory is informational.
- The registry is healthy when every readable top-level JSON record names a
  live PID.
- A proven-dead PID produces a warning that names the stale record.
- Malformed records, unknown fields, and nested artifacts such as `leases/`
  remain opaque to Core.

Use `vaultspec-core spec doctor --json` when attaching diagnostic output to an
issue. Remove or reclaim a stale record only through its producer. The doctor
command never repairs, removes, or rewrites process records or lease markers.
See the [CLI reference](CLI.md) for command output contracts. Report unresolved
integration problems in the
[VaultSpec Core issue tracker](https://github.com/nevenincs/vaultspec-core/issues)
with the doctor JSON, operating system, and producer version.

## Related documentation

| Document                          | What it covers                                      |
| --------------------------------- | --------------------------------------------------- |
| [Repository README](../README.md) | Project overview, installation, and getting started |
| [CLI reference](./CLI.md)         | Every command, flag, and option for vaultspec-core  |
| [MCP reference](./MCP.md)         | The MCP server tools, setup, and configuration      |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/nevenincs/vaultspec-core/issues).
