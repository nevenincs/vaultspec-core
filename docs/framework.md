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
pre-commit, run `pre-commit install` to activate it. The generated hooks check the whole
vault rather than only staged files, and never modify documents.

Use the [pre-commit controls](CLI.md#vaultspec-core-spec-precommit) to enable or disable
configuration generation. These settings don't remove an existing configuration or
deactivate an installed hook.

**MCP clients.** Check enrollment with `vaultspec-core spec mcps status --json`. See the
[MCP tool reference](./MCP.md#tools) for the available tools.

**Agent-runtime hooks.** Write a hook once and Core renders it for every coding agent
you have installed. See [agent-runtime hooks](#agent-runtime-hooks).

## Agent-runtime hooks

Claude Code, Codex, the Antigravity CLI and the Gemini CLI can each run a shell command
when something happens in a session: before a tool runs, after it returns, when a
session starts. Each one spells the events differently and keeps them in a different
file. Write the hook once in `.vaultspec/hooks/`, and `vaultspec-core sync` renders it
into whichever of those agents this project has installed.

These are the agent's events, not Core's. A hook here fires inside the coding agent
while you work. It has nothing to do with the
[pre-commit hooks](#configure-project-integrations) Core scaffolds for Git, nor with the
lifecycle triggers in `.vaultspec/triggers/`, which fire inside Core's own CLI. Each
directory has one owner, so a file in the wrong one is reported rather than silently
ignored.

The two systems are approved separately, and both `vaultspec-core spec hooks status` and
`vaultspec-core spec triggers status` report a `hooks_dir` and a `triggers_dir`
respectively in `--json`. Same shape, different directory: read the command, not just
the key.

### Write a hook

One YAML file per hook, in `.vaultspec/hooks/`. The filename stem is the hook's name.
There's no command that scaffolds one; create the file yourself.

Install creates the directory empty and Core ships no example in it, deliberately. A
file here is a shell command, and anything bundled would arrive in every install of
every project — disabled or not, one edit away from running.

```yaml
# .vaultspec/hooks/guard-commands.yaml
event: pre_tool_use
matcher: Bash
command: "./scripts/audit-command.sh"
timeout: 30
enabled: true
```

| Key       | Required | Meaning                                                         |
| --------- | -------- | --------------------------------------------------------------- |
| `event`   | yes      | One of the canonical events below                               |
| `command` | yes      | The shell command the agent runs                                |
| `matcher` | no       | Tool-name pattern to filter on; empty matches every tool        |
| `timeout` | no       | Seconds, always. Core converts to each provider's unit          |
| `enabled` | no       | Defaults to `true`; `false` parses the file but renders nothing |

This directory holds agent-runtime hooks only. Core's own lifecycle triggers live in
`.vaultspec/triggers/`, and a file whose `event` isn't one of the canonical names below
doesn't belong here.

### Canonical events

Write the canonical name. Core translates it to each provider's own spelling. The table
below is Core's mapping: a dash means Core renders nothing for that provider, and the
hook is skipped there with a warning naming the hook and the provider.

| Canonical event      | claude             | codex              | antigravity   | gemini         |
| -------------------- | ------------------ | ------------------ | ------------- | -------------- |
| `pre_tool_use`       | `PreToolUse`       | `PreToolUse`       | `PreToolUse`  | `BeforeTool`   |
| `post_tool_use`      | `PostToolUse`      | `PostToolUse`      | `PostToolUse` | `AfterTool`    |
| `session_start`      | `SessionStart`     | `SessionStart`     | -             | `SessionStart` |
| `session_end`        | `SessionEnd`       | `SessionEnd`       | -             | `SessionEnd`   |
| `stop`               | `Stop`             | `Stop`             | `Stop`        | -              |
| `user_prompt_submit` | `UserPromptSubmit` | `UserPromptSubmit` | -             | -              |
| `notification`       | `Notification`     | -                  | -             | `Notification` |

A dash is not a statement about the provider. It says only that Core has no mapping, and
in some cases the provider does have an equivalent Core doesn't use yet. Treat the table
as what Core does, and each provider's own hooks documentation as what that provider
supports.

`pre_tool_use` and `post_tool_use` are the only two events every provider runs. Bind a
hook that has to work everywhere to one of those.

Antigravity fires five events and Core maps three of them. Its other two,
`PreInvocation` and `PostInvocation`, are the nearest thing it has to a session
boundary, but they expect a different response shape, so Core leaves them unmapped
rather than render something the agent would fail to parse. If you previously bound a
hook to `session_start` or `session_end` expecting it to reach Antigravity, it never
did: those names exist nowhere in the `agy` binary, so the hook rendered and was never
called.

Gemini expresses hook timeouts in milliseconds and every other provider in seconds.
Write seconds; Core multiplies where it has to.

### Where they land

| Provider    | Rendered into                        | How Core marks its own entries  |
| ----------- | ------------------------------------ | ------------------------------- |
| claude      | `.claude/settings.json`, `hooks` key | `.claude/.vaultspec-hooks.json` |
| codex       | `.codex/hooks.json`                  | `.codex/.vaultspec-hooks.json`  |
| antigravity | `.agents/hooks.json`                 | The `vaultspec` hookset         |
| gemini      | `.gemini/settings.json`, `hooks` key | `.gemini/.vaultspec-hooks.json` |

Core reads and writes `.codex/hooks.json` only. Codex also accepts an inline `[hooks]`
table in `.codex/config.toml`; Core neither reads that nor reports it, so hooks you put
there are invisible to `vaultspec-core spec hooks status`.

Under `--target`, hooks and triggers resolve differently, and it isn't an oversight.
Hooks are source content, like rules and skills: they're read from the workspace you run
the command in and written into the target. Triggers are read from the target, because a
trigger reacts to something that happened to that workspace.

Hooks you wrote into those files by hand are preserved. Core records exactly what it
wrote last sync in the sidecar beside the file, so the next sync removes precisely its
own previous entries and leaves everything else alone. The record sits in a sidecar
rather than inside the file because some providers reject a hooks file carrying any key
they don't recognize, and would discard the whole thing.

Antigravity needs no sidecar: it groups hooks under named hooksets, and Core owns the
one called `vaultspec`.

Don't edit the sidecars. Deleting one makes Core forget what it wrote, so the entries
from before become indistinguishable from yours. The next sync re-adopts the ones it
still renders and abandons the rest in place, where nothing will clean them up.

### Approve before they render

A hook file travels with the repository, and rendering one writes a command into your
agent's own configuration, where it runs as you on every matching tool call rather than
once per sync. So Core renders nothing until you have approved it on this machine.

You are asked before any sync that would render, and before
`vaultspec-core install --upgrade`. Not on a fresh install, which has nothing to render
yet, and never under `--skip hooks`. For each unapproved hook you see its name, its
path, the event, the matcher, and the command exactly as written, then a single prompt
that defaults to no.

Declining costs only the hooks. The sync itself completes, the hook isn't rendered, and
stderr names the files it skipped and the command that approves them.

Approval is recorded outside the workspace, in `~/.vaultspec/hook-trust.json`, and
pinned to each file's current contents. Editing an approved hook, or pulling a change to
one, withdraws the approval until you grant it again. Nothing a clone or an archive
carries can add an entry there.

Where there is no operator to ask, nothing renders. `--json` output, `CI`, a redirected
stream, `VAULTSPEC_NON_INTERACTIVE`, and MCP tool calls all skip the prompt, skip the
rendering, and write nothing to the ledger. There's no flag that approves on your
behalf, because a flag a script can pass is a flag a repository can talk a script into
passing. The refusal lives in the renderer rather than in the prompt, so a route that
never reaches a prompt still cannot render an unapproved hook.

To withdraw approval, run `vaultspec-core spec hooks trust --revoke` and sync: the next
sync removes the entries it had written, so the hook leaves the provider's config rather
than lingering there unapproved.

Triggers are approved separately, with
[`vaultspec-core spec triggers trust`](CLI.md#vaultspec-core-spec-triggers). Approving
one system never approves the other.

### Turn it off

`vaultspec-core sync --skip hooks` runs every other sync pass and leaves hook rendering
alone. It doesn't remove hooks an earlier sync already rendered; it declines to
reconcile them. `vaultspec-core install --skip hooks` does the same during install.

Removing a source file and syncing is the way to withdraw a rendered hook. A config file
that held nothing but hooks Core wrote is removed along with them rather than left
behind empty; one that carries your own settings keeps them and loses only the hooks.

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
