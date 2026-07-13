---
tags:
  - '#research'
  - '#operator-cli-sync-authority'
date: '2026-05-15'
modified: '2026-06-13'
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-reference]]'
---

# `operator-cli-sync-authority` research: `sync authority and command-shape ambiguity`

Research into follow-up operator feedback about the `sync` command family.
Scope covers broad versus narrow synchronization semantics, provider-facing
generated stubs, CLI wording drift, and regression coverage needed to prevent
future command-shape ambiguity.

## Findings

### Operator-facing ambiguity

The CLI has two visible sync shapes:

- `vaultspec-core sync`
- `vaultspec-core spec <resource> sync`

The operator mental model is that `vaultspec-core sync` synchronizes the
`.vaultspec/` source of truth to enrolled provider outputs. That is also the
correct broad behavior: root sync can run rules, skills, agents, system prompt,
config stub, and MCP passes unless explicitly skipped.

The narrow `spec` commands are specialized resource operations:

- `vaultspec-core spec rules sync`
- `vaultspec-core spec skills sync`
- `vaultspec-core spec agents sync`
- `vaultspec-core spec system sync`
- `vaultspec-core spec mcps sync`

The dangerous part is not that narrow commands exist. The dangerous part is
that they share the plain verb `sync`, use similar help wording, and do not make
their narrower scope obvious at the moment an operator is trying to propagate a
source-side change.

### Current implementation facts

`vaultspec-core sync --help` accepts provider targets `all`, `claude`,
`gemini`, `antigravity`, and `codex`. The value `core` is rejected because sync
reads from `.vaultspec/`; `core` belongs to install and uninstall semantics, not
sync provider semantics.

Root sync executes resource passes for rules, skills, agents, system prompts,
provider config stubs, and MCPs unless skipped. The short root help and CLI
reference omit MCPs from the broad sync description, which creates drift between
the implemented behavior and the operator-facing contract.

`vaultspec-core spec rules add` creates a source rule under
`.vaultspec/rules/rules/`. It does not update provider-facing outputs and its
human output does not tell the operator to run `vaultspec-core sync` afterward.

Provider-facing config stubs are generated artifacts:

- `CLAUDE.md` for Claude.
- `GEMINI.md` for Gemini and Antigravity.
- `AGENTS.md` and `.codex/config.toml` for Codex.

MCP sync is not a directory-style provider sync. It is provider-agnostic
`.mcp.json` merge behavior, so narrow MCP wording must not imply the same
destination model as rules, skills, agents, or system prompt files.

### Drift and risk

The documentation says `vaultspec-core sync` or
`vaultspec-core spec <resource> sync` can propagate edits, but it does not
explain broad sync authority versus narrow resource-scoped maintenance. This
makes the wrong command feel plausible after adding a rule.

The confirmed failure mode is:

1. Add or edit a source rule.
1. Run `vaultspec-core spec rules sync`.
1. Observe that root provider stubs such as `AGENTS.md`, `CLAUDE.md`, and
   `GEMINI.md` remain stale.
1. Run top-level `vaultspec-core sync`.
1. Observe that provider stubs update.

That result means top-level sync behaves correctly, but the surrounding command
shape encourages operator error and stale generated outputs.

### External design anchors

CLI Guidelines emphasizes human-first command output, explicit state-change
reporting, and machine-readable output for automation. Source:
https://clig.dev/

Microsoft System.CommandLine design guidance says command groups should group
subcommands, action commands should carry clear verb semantics, and command
contracts are hard to change after users script them. Source:
https://learn.microsoft.com/en-us/dotnet/standard/commandline/design-guidance

GNU command-line standards emphasize consistency in option names and interface
shape so users have fewer idiosyncrasies to remember. Source:
https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces

### Implications

`vaultspec-core sync` should be the only authoritative synchronization surface
for producing a complete provider-facing workspace from `.vaultspec/`.

Narrow `spec <resource> sync` commands should either delegate to shared sync
implementation with no duplicated policy, or be reframed as advanced
resource-scoped maintenance commands whose help and runtime output state that
they do not perform a complete provider-facing refresh.

`vaultspec-core spec rules add` should tell the operator exactly what changed
and what remains stale: the source rule was created under
`.vaultspec/rules/rules/`, provider-facing outputs were not updated, and the
normal next command is `vaultspec-core sync`.

Regression coverage should prove that adding a rule followed by top-level sync
updates `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`, and that CLI help cannot
again drift into presenting narrow sync as an equivalent alternative.
