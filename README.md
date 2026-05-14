# vaultspec-core

[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](./pyproject.toml)
[![Continuous integration](https://github.com/wgergely/vaultspec-core/actions/workflows/ci.yml/badge.svg)](https://github.com/wgergely/vaultspec-core/actions/workflows/ci.yml)
[![Docker](https://github.com/wgergely/vaultspec-core/actions/workflows/docker.yml/badge.svg)](https://github.com/wgergely/vaultspec-core/actions/workflows/docker.yml)
[![Model Context Protocol](https://img.shields.io/badge/MCP-vaultspec--mcp-informational)](./.vaultspec/MCP.md)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

______________________________________________________________________

## A research-driven framework for coding agents with a paper trail

Vaultspec is a spec-driven development rulebook for artificial intelligence (AI) coding agents. It enforces a structured pipeline around AI-assisted development: research, decide, plan, execute, and review.

Each stage writes durable markdown artifacts in your repository. AI coding agents use those records to share context, and you use them to track development progress.

______________________________________________________________________

## How it works

vaultspec-core structures AI-assisted development into a repeatable pipeline centered around `features`. Two directories form the backbone:

- **`.vaultspec/`** holds the framework configuration - rules, templates, agent personas, and system prompts that shape how AI tools behave.
- **`.vault/`** is the paper trail - research notes, architecture decision records (ADRs), implementation plans, execution logs, and review and audit trails.

Two entry points ship with the framework:

- **`vaultspec-core`** is the command-line interface (CLI) that manages your workspace. It installs, syncs, and validates framework resources. See the [CLI reference](./.vaultspec/CLI.md) for the full command surface.
- **MCP server** exposes vault discovery and document creation to Model Context Protocol (MCP) clients like Claude Code. Invoke it with `uv run python -m vaultspec_core.mcp_server.app`. A `vaultspec-mcp` console script is also installed, but module invocation avoids binary locking on Windows. See the [MCP reference](./.vaultspec/MCP.md) for setup and tool documentation.

The [framework manual](./.vaultspec/README.md) walks through the development workflow and explains how to customize rules, skills, agents, and system prompts.

______________________________________________________________________

## Getting started

### Prerequisites

- Python 3.13 or later
- `pip` for the published package, or [uv](https://github.com/astral-sh/uv) for source development

### Install

Install the published package:

```bash
pip install vaultspec-core
vaultspec-core --version
```

For source development:

```bash
git clone https://github.com/wgergely/vaultspec-core.git
cd vaultspec-core
uv sync
uv run vaultspec-core --version
```

### Initialize a workspace

```bash
vaultspec-core install --target ./my-project
```

This scaffolds `.vaultspec/` and `.vault/` inside the target directory. It seeds builtin resources such as rules, agents, skills, system prompts, templates, hooks, and MCP definitions. It also syncs generated provider resources to the configured provider destinations and writes an `.mcp.json` for MCP-capable clients.

To install the framework plus one provider destination:

```bash
vaultspec-core install claude --target ./my-project
```

After editing any framework files under `.vaultspec/`, re-sync to push changes to provider destinations:

```bash
vaultspec-core sync
```

### Start using it

Open your AI tool in the project directory. The `install` step synced rules, skills, system prompts, and agent personas into provider-specific destinations such as `.claude/`, `.gemini/`, shared `.agents/`, and `.codex/`. It also wrote an `.mcp.json` for MCP-capable clients. Your AI tool will pick these up automatically.

The framework requires research and architectural decisions before coding begins. Describe what you want to build in natural language:

> "Research options for adding full-text search to the API"

The synced rules guide the AI through the pipeline. They produce structured research findings in `.vault/research/`, then progress through architectural decisions, planning, execution, and review. Each stage writes records to `.vault/` and references the output of earlier stages.

You can also invoke skills explicitly to start a specific stage. The bundled skills (`vaultspec-research`, `vaultspec-adr`, `vaultspec-write`, `vaultspec-execute`, `vaultspec-code-review`) read the relevant vault records and structure the AI's output accordingly.

The [framework manual](./.vaultspec/README.md) walks through each stage in detail with examples.

______________________________________________________________________

## The development workflow

Every feature flows through five stages. The AI does the analytical work; you approve each checkpoint before the next stage starts.

| Stage        | You                                          | The AI                                  |
| ------------ | -------------------------------------------- | --------------------------------------- |
| **Research** | Review and approve the findings              | Explores the problem, documents options |
| **Decide**   | Approve the decision record                  | Drafts an ADR based on research         |
| **Plan**     | Review and approve the implementation plan   | Breaks the decision into concrete steps |
| **Execute**  | Stay available if the AI gets stuck          | Works through each step autonomously    |
| **Review**   | Read the report and decide if the work ships | Audits the result, flags any issues     |

Everything produced - findings, ADRs, plans, execution records, and review reports - is saved in `.vault/`.

______________________________________________________________________

## Working with the vault

The `vaultspec-core vault` command group manages documents in `.vault/`. A few common operations:

```bash
# Scaffold a new document from a template
vaultspec-core vault add research --feature search-api

# List and inspect documents
vaultspec-core vault list --feature search-api
vaultspec-core vault stats --feature search-api

# Validate frontmatter, links, and cross-references (--fix to auto-repair)
vaultspec-core vault check all --fix

# Visualize the dependency graph for a feature
vaultspec-core vault graph --feature search-api
```

Valid document types are `adr`, `audit`, `exec`, `plan`, `reference`, and `research`. Generated feature indexes live in `.vault/index/` and are managed by `vaultspec-core vault feature index`. See the [CLI reference](./.vaultspec/CLI.md#vault-commands) for the full command surface.

______________________________________________________________________

## Schema migrations

When a release of `vaultspec-core` changes the on-disk shape of `.vault/`, a versioned migration registry delivers the new layout. The registry replaces recurring pre-commit migration hooks. Each registered migration runs once per upgrade and never again.

Three triggers cover every consumer path:

- `vaultspec-core install --upgrade` runs every pending migration after re-seeding builtins.
- Any `vaultspec-core vault ...` command, for example `vaultspec-core vault add`, `vaultspec-core vault feature index`, or `vaultspec-core vault check`, lazily applies pending migrations before its primary action.
- `vaultspec-core migrations status` and `vaultspec-core migrations run` give explicit control for operators who prefer manual application.

The lazy path keeps consumers current even if they never run `vaultspec-core install --upgrade`.

The registry compares each migration's `target_version` against the workspace manifest's `vaultspec_version`. Entries whose target exceeds the manifest run in version order. The manifest version is bumped only after success. A migration that fails leaves the manifest version unchanged, so the next invocation re-attempts it.

______________________________________________________________________

## Further reading

| Guide                                      | What it covers                                        |
| ------------------------------------------ | ----------------------------------------------------- |
| [Framework manual](./.vaultspec/README.md) | Development workflow, skills, and customization       |
| [CLI reference](./.vaultspec/CLI.md)       | All commands, flags, and options for `vaultspec-core` |
| [MCP reference](./.vaultspec/MCP.md)       | MCP server tools, setup, and configuration            |

### Getting help

Open an issue on [GitHub](https://github.com/wgergely/vaultspec-core/issues).

______________________________________________________________________

## Contributing and license

We welcome bug reports, feature ideas, and pull requests. Browse what's in progress on [GitHub Issues](https://github.com/wgergely/vaultspec-core/issues).

vaultspec-core is released under the [MIT License](./LICENSE).
