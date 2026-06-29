# vaultspec-core

[![Continuous integration](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml/badge.svg)](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/vaultspec-core.svg)](https://pypi.org/project/vaultspec-core/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-vaultspec--mcp-informational)](./docs/MCP.md)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

______________________________________________________________________

**Vaultspec is a spec-driven harness for coding agents (and us, the humans).**

______________________________________________________________________

Vaultspec guides agents through a
`Research → Decide → Plan → Code → Verify` pipeline not dissimilar to other spec driven
frameworks (Superpowers!)

All work leaves a papertrail in the project's `.vault`. Documents are bound together by tags,
and references. Together, they represents the project's decision and execution history.

> [!TIP]
> The vault is plain Markdown with wiki-links, so it opens directly in
> [Obsidian](https://obsidian.md). Point an Obsidian vault at `.vault/` and its feature
> tags and document links render as a navigable graph network.

## What is included?

`vaultspec-core` implements the natural language description of the workflow. It ships rules,
skills and agents, and a CLI to manage vault health, planning and rules. See
[framework manual](./docs/framework.md) for more info.

> [!TIP]
> The framework favours semantic search via the core's optional sister project,
> [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag)

## Getting started

### 1. Install

For the quickest, dependency-free project bootstrap, run from a git project folder:

```bash
uvx vaultspec-core install
```

Use it as a tool or dependency:

```bash
# You can add it as a local tool
uv tool install vaultspec-core

# Or a project dependency
uv add vaultspec-core
```

### 2. Bootstrap

```bash
uv run --no-sync vaultspec-core install [--upgrade]
```

See the [CLI reference](./docs/CLI.md) for installation options.

> [!NOTE]
> `vaultspec-core install` handles project integration separately: it
> manages a block in your `.gitignore` and `.gitattributes`, writes pre-commit hooks,
> and drops an `.mcp.json` for Model Context Protocol clients by deafult.

## Vault + Spec

The harness supports Claude, Codex, Gemini/Angtigravity.

All development paper trail live in `.vault` as markdown files.
Rules, agents, skills are seeded from the `.vaultspec` via:

```bash
uv run --no-sync vaultspec-core sync
```

> [!TIP]
> Make sure to run
>
> ```bash
> uv run --no-sync vaultspec-core install --upgrade
> ```
>
> after a library update as the shipped agent, skill and rules
> might change between library versions.

## The pipeline at a glance

The pipeline breaks down into these steps:
`[R] Research  →  [D] Decide (ADRs)  →  [P] Plan  →  [C] Code  →  [V] Verify`.
Each step ships with their skills, agents and CLI verbs.

To start using the framework describe the work you want done in natural language:

> "Start a new vaultsepc pipeline to research options for adding full-text search to the API."

The synced rules guide the agent through the pipeline stage by stage, writing documents
into `.vault/` as it goes: a research note, then a decision record, a plan, execution
records, and a final review. You approve each checkpoint before the agent moves on.

Invoke a stage skill directly - for example `/vaultspec-research` - to enter the
pipeline at a specific stage. See [framework manual](./docs/framework.md) for how each one works.

### Skills

Skills are the slash-commands that drive each stage of the pipeline. Six map to the
pipeline stages; two helpers - curate and documentation - cover everyday upkeep. The
[framework manual](./docs/framework.md) gives full guidance on each, plus two further
skills for team coordination and project management.

**Which skill, when**

| When you want to                              | Skill                      |
| :-------------------------------------------- | :------------------------- |
| Explore a problem and weigh options           | `/vaultspec-research`      |
| Ground the work in the existing codebase      | `/vaultspec-code-research` |
| Record the decision and its consequences      | `/vaultspec-adr`           |
| Turn the decision into an implementation plan | `/vaultspec-write`         |
| Work through the plan, step by step           | `/vaultspec-execute`       |
| Audit the finished work by severity           | `/vaultspec-code-review`   |
| Repair vault links, frontmatter, and naming   | `/vaultspec-curate`        |
| Draft user-facing documentation               | `/vaultspec-documentation` |

### MCP server

We ship an MCP but the current implementation strongly favours direct cli calls.
[MCP reference](./docs/MCP.md) for setup and available tools.

## Tips

### Managing documents from the CLI

Documents are created and maintained through the `vaultspec-core vault` command group -
never hand-written. The CLI enforces templates, tag taxonomy, and wiki-link resolution
so your vault stays consistent.

```bash
# Scaffold a document from a template
vaultspec-core vault add research --feature search-api

# Find and inspect documents
vaultspec-core vault list --feature search-api

# Validate frontmatter, links, and cross-references (--fix to auto-repair)
vaultspec-core vault check all --fix

# Visualize a feature's dependency graph
vaultspec-core vault graph --feature search-api
```

Plans carry deeper structure - waves, phases, and steps. The
[framework manual](./docs/framework.md) covers that structure.

## Learn more

| Guide                                   | What it covers                                              |
| --------------------------------------- | ----------------------------------------------------------- |
| [Framework manual](./docs/framework.md) | The development workflow, skills, agents, and customization |
| [CLI reference](./docs/CLI.md)          | Every command, flag, and option for vaultspec-core          |
| [MCP reference](./docs/MCP.md)          | The MCP server tools, setup, and configuration              |

The companion projects extend the framework:
[vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) adds semantic search over
your vault and codebase,
[vaultspec-dashboard](https://github.com/nevenincs/vaultspec-dashboard) provides a
visual UI, and [vaultspec-a2a](https://github.com/nevenincs/vaultspec-a2a) handles agent
orchestration.

## Status, help, and license

vaultspec-core is actively developed. The version badge shows the current release. File
bugs and questions on the
[issue tracker](https://github.com/nevenincs/vaultspec-core/issues). Bug reports,
feature ideas, and pull requests are welcome. vaultspec-core is released under the
[MIT License](./LICENSE).
