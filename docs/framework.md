# Run the Vaultspec workflow

Start from a [configured project](../README.md#install), then describe your task to the
coding agent. You don't need to create a complete set of documents before work begins.
This guide covers choosing the route, authorizing work, and continuing it across
sessions.

Commands here use `vaultspec-core`; keep the `uvx` or `uv run` prefix if that is how you
installed it.

<p id="begin-a-pipeline"></p>

## Choose the route for your task

Describe the outcome and use a feature tag to group its records, as in the
[README example](../README.md#start-a-feature). The agent assesses two separate needs:

- **Decision coverage:** does the work depend on a costly-to-reverse choice? Reuse an
  accepted architecture decision record (ADR), or gather evidence and propose a new or
  amended decision.
- **Planning:** does scope or progress need to survive sessions or handoff? If so, write
  a plan; otherwise work directly.

A typo fix can proceed directly. A multi-session cleanup within settled design choices
can need a plan but no new ADR. Changing a persisted data format needs a decision even
if the implementation is short. File count alone does not determine the route.

Search for existing decisions across features, not only under the current tag. Reuse
applicable evidence and accepted ADRs instead of creating equivalent records.

<p id="how-a-feature-flows-into-the-vault"></p>

## Workflow stages

Use these skills when you want to request a particular part of the workflow:

| Need                           | Skill                     | Record                                          |
| ------------------------------ | ------------------------- | ----------------------------------------------- |
| Weigh options using evidence   | `vaultspec-research`      | Research: findings and sources                  |
| Understand how real code works | `vaultspec-code-research` | Reference: implementation patterns              |
| Record a costly decision       | `vaultspec-adr`           | ADR: the choice, rationale, and consequences    |
| Preserve scope and work order  | `vaultspec-write`         | Plan: cohesive, verifiable Steps                |
| Carry out an approved plan     | `vaultspec-execute`       | Ledger: changed files and verification per Step |
| Review planned work            | `vaultspec-code-review`   | Audit: findings and their resolutions           |

These are skill names for your agent, not shell commands. Research, code References, and
Audit findings can supply decision evidence; you don't need all three. Each record has
one job. Keep evidence in its source record and link to it rather than copying it into
decisions and plans.

## Orient: see what is in flight

From your repository, check current plan progress, next open steps, and recent changes:

```bash
vaultspec-core status
```

Once a feature has a plan, use its feature tag to trace its plans, steps, and recorded
execution evidence. Replace `search-api` with your feature tag:

```bash
vaultspec-core status search-api
```

To narrow the view to one plan, supply its stem or path instead.

The `>` marker identifies the next open step. If an open step shows `no rows`, it lacks
recorded execution evidence; that doesn't prove no work occurred.

See the [status reference](CLI.md#vaultspec-core-status) for output details and options.

## Approve the scope, not every edit

Approve new or changed decisions before implementation relies on them, and approve a
plan before its Steps execute. Review the proposed scope and choices, not only the
document's status label.

Explicit prior authorization can cover later work within that scope. The agent records
its basis and proceeds with ordinary implementation details and in-scope corrections.
Material scope changes, uncovered costly decisions, and actions needing new external
authority require your input. Not every correction needs another approval turn.

## Find a feature's documents

List a feature's records:

```bash
vaultspec-core vault list --feature search-api
```

See the [list reference](CLI.md#vaultspec-core-vault-list) for type filters and
pagination.

For semantic search, [install RAG](https://github.com/nevenincs/vaultspec-rag#install)
and [index your project](https://github.com/nevenincs/vaultspec-rag#use-it) first. RAG
is a separate package; Core doesn't install it.

```bash
vaultspec-rag search "full-text ranking and tokenizer" --type vault
```

## Find and amend an ADR

List the current feature's ADRs with:

```bash
vaultspec-core vault list adr --feature search-api
```

Omit `--feature` to inspect decisions recorded elsewhere in the project.

For prose edits, follow [editing safely](syntax.md#editing-safely). Amend an existing
ADR for refinements, narrower scope, or parameter changes. Keep the accepted content
intact while presenting a proposed amendment separately; apply it after approval.

If the direction reverses or the rationale no longer applies, create a replacement ADR.
The replacement must be accepted before
[superseding the old ADR](CLI.md#vaultspec-core-vault-adr-supersede).

Superseding doesn't revise plans or retarget their authorizing links. Review affected
active plans and links, revise them where necessary, and establish decision coverage
before continuing implementation. Completed plans retain their historical links;
reopening work requires reassessment.

## Make a plan

When the work needs durable sequencing, ask for a plan:

> Use vaultspec-write to plan the search-api work. Reuse applicable decisions and keep
> the plan to a few major, verifiable Steps.

Before approving the plan, review its scope, work order, affected files, and
verification steps. If it doesn't match the approved scope, ask for revisions before
execution.

A Step describes a cohesive change, which may span several files. Start with a flat L1
plan; add Phases, Waves, or an Epic only when those groups help coordinate the work.
Link governing ADRs and inherit their evidence through those links. If none governs,
record why no costly decision is involved in the plan's Description.

For parallel work, name each worker's assignment and keep write ownership separate.
Sharing a working tree requires coordination of shared metadata and commits. More
workers do not, by themselves, require a higher plan tier.

For the plan's structure and Step syntax, see [tiers](syntax.md#tiers) and
[row format](syntax.md#row-format).

## Change a plan safely

Use `vaultspec-core vault plan` to add, move, or remove Steps and their containers. Keep
structural edits out of your text editor.

Before reorganizing existing work, review the [identifier rules](syntax.md#identifiers).
See [plan commands](CLI.md#vaultspec-core-vault-plan) for arguments and examples.

## Execute a plan

After approving the plan, ask your agent to use `vaultspec-execute`. It starts from the
next open Step. For each Step, it implements, runs relevant tests and checks, logs the
changed files and verification results, marks the Step complete, and commits.

To resume interrupted work, ask the agent to continue or specify a Step. Use
[status](CLI.md#vaultspec-core-status) to check progress and the next open Step.

If a closed Step is incomplete, reopen it with `vaultspec-core vault plan step uncheck`
and keep its execution records. See the
[plan commands](CLI.md#vaultspec-core-vault-plan) for arguments and other state changes.

## Review the result

Ask your agent to use `vaultspec-code-review` to compare the implementation with the
plan and any governing decisions. Review the integrated result, not individual files as
separate approval gates. The [review guide](./correctness.md) covers when review is due,
how findings are recorded, and how fixes are verified.

<p id="everyday-commands"></p>

## Check records and project health

Use the [verification guide](verification.md) to check installation, validate records,
and review repairs. These checks validate the workspace and records; they don't replace
implementation tests or review.

To inspect a feature's document links, replace `search-api` with its feature tag:

```bash
vaultspec-core vault graph --feature search-api
```

See the [graph reference](CLI.md#vaultspec-core-vault-graph) for filtering and output
options.

## Customize the policy

Add a project rule with its instructions:

```bash
vaultspec-core spec rules add enforce-newline --body "All workspace source files must end with a single trailing newline."
```

Edit `.vaultspec/rules/enforce-newline.md` to change the instructions. Then update the
enabled coding-agent integrations:

```bash
vaultspec-core sync
```

Review and commit the policy changes. For skills, agents, and other rule operations, see
the
[resource commands](CLI.md#vaultspec-core-spec-rules--vaultspec-core-spec-skills--vaultspec-core-spec-agents).

For setup and upgrades, see [installation options](#installation-options). To remove
Core from a project, follow the [uninstall reference](CLI.md#uninstall).

## Installation options

The quickstart uses `uvx vaultspec-core install`. When using this route, keep the `uvx`
prefix for later commands.

To install the CLI once and run it from any project:

```bash
uv tool install vaultspec-core
vaultspec-core install
```

To manage it as a project dependency:

```bash
uv add vaultspec-core
uv run vaultspec-core install
```

Contributors then use `uv sync` to install dependencies and `uv run vaultspec-core` to
run the CLI. Configure generated launchers under
[project integrations](#configure-project-integrations). For release binaries that need
neither a separate Python install nor a network, see [Homebrew and Scoop](channels.md).

After updating the package, run `vaultspec-core install --upgrade` in each project to
update its bundled rules, skills, and agents. Use `uvx` or `uv run` as appropriate for
your installation route.

<p id="decisions-you-make-once"></p>

## Configure project integrations

**Install mode.** Choose how generated hooks and MCP configuration launch Core with
`vaultspec-core install --mode`. See the [install reference](CLI.md#install) for modes
and selection rules.

**Pre-commit hooks.** Generated configuration doesn't activate a Git hook. If you use
pre-commit, run `pre-commit install` to activate it. Vault checks and annotation cleanup
aren't limited to staged files; cleanup modifies documents. Review changes before
committing.

Use the [pre-commit controls](CLI.md#vaultspec-core-spec-precommit) to enable or disable
configuration generation. These settings don't remove an existing configuration or
deactivate an installed hook.

**MCP clients.** Check enrollment with `vaultspec-core spec mcps status --json`. See the
[MCP tool reference](./MCP.md#tools) for the available tools.

<p id="machine-global-runtime-state"></p>

<p id="what-an-absent-managed-file-means"></p>

## Manage generated files

Commit your feature documents in `.vault/` and your project rules, skills, agents, and
workspace policy in `.vaultspec/`. Include `.vaultspec/workspace.json` so the policy
travels with the project. The managed `.gitignore` entries exclude local caches, logs,
and state.

Use the [Gitignore](CLI.md#vaultspec-core-spec-gitignore),
[Gitattributes](CLI.md#vaultspec-core-spec-gitattributes), and
[Precommit](CLI.md#vaultspec-core-spec-precommit) controls to set project policy for
those files.

Enabling or disabling changes only workspace policy; it doesn't edit or remove existing
files. Disabling Precommit also leaves any active Git hook installed.

Deleting a managed Git block or the pre-commit YAML stops ordinary sync from managing
that output locally. Install or upgrade can recreate it unless project policy disables
generation.

For [Model Context Protocol (MCP)](MCP.md), edit the canonical JSON server definitions.
Core merges Vaultspec-owned entries into enabled provider configurations and preserves
unrelated entries.

## Per-account runtime state

`~/.vaultspec/` stores per-account runtime state shared across repositories. Project
policy stays in the repository's `.vaultspec/` directory.

To diagnose runtime state, run:

```bash
vaultspec-core spec doctor --json
```

The process-registry check reports records in `~/.vaultspec/procs/` whose processes no
longer run. It doesn't modify those records. Don't delete runtime records by hand. If
the check reports a stale record, include the JSON output in a
[bug report](https://github.com/nevenincs/vaultspec-core/issues).

## Related documentation

| Document                                               | What it covers                                     |
| ------------------------------------------------------ | -------------------------------------------------- |
| [Repository README](../README.md)                      | What vaultspec-core is, and installing it          |
| [Document syntax](./syntax.md)                         | Frontmatter, tags, links, and the plan row grammar |
| [Verifying a workspace and a vault](./verification.md) | The health commands and what each check proves     |
| [Review a feature implementation](./correctness.md)    | Review scope, findings, fixes, and test evidence   |
| [CLI reference](./CLI.md)                              | Every command, flag, and option                    |
| [MCP reference](./MCP.md)                              | The MCP server tools, setup, and configuration     |

For bug reports and feature requests, open an issue on the
[vaultspec-core issue tracker](https://github.com/nevenincs/vaultspec-core/issues).
