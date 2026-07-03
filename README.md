<div align="center">

<img src="docs/assets/logo.png" alt="vaultspec logo" width="150" />

# vaultspec-core

**Vaultspec is a spec-driven harness for coding agents (and us, the humans).**

[![Continuous integration](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml/badge.svg)](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/vaultspec-core.svg)](https://pypi.org/project/vaultspec-core/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-vaultspec--mcp-informational)](./docs/MCP.md)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

[Getting started](#getting-started) · [The pipeline](#the-pipeline-at-a-glance) ·
[Framework manual](./docs/framework.md) · [CLI reference](./docs/CLI.md) ·
[MCP](./docs/MCP.md)

</div>

<p align="center">
<img src="docs/assets/demo.gif" alt="vaultspec pipeline demo - provisioning a project, scaffolding research, ADR, and plan, then checking and graphing the vault" width="880" />
</p>

Vaultspec guides agents through a `Research → Decide (ADRs) → Plan → Code → Verify`
pipeline, not dissimilar to other spec-driven frameworks (Superpowers!) - with one
difference: nothing is throwaway. All work leaves a papertrail in the project's
`.vault`. Documents are bound together by feature tags and wiki-link references.
Together, they represent the project's decision and execution history - a second brain
your agents read before they write.

We hold ourselves to it, too: vaultspec-core is developed with vaultspec. Its own
`.vault` currently holds 800+ CLI-scaffolded documents across 100+ features, and every
terminal render on this page is real output against that live vault:

<p align="center">
<img src="docs/assets/term-status.svg" alt="vaultspec-core status - live output from this repository's own vault" width="880" />
</p>

## What is included?

`vaultspec-core` implements the natural language description of the workflow, and the
machinery that enforces it:

- **Rules, skills, and agent personas** for Claude, Codex, Gemini, and Antigravity,
  seeded from one `.vaultspec` source of truth and synced per provider.
- **A CLI** that scaffolds, audits, and repairs every vault document - templates, tag
  taxonomy, wiki-link resolution, and plan structure are enforced, never hand-written.
- **Structured plans** that scale with the work: four complexity tiers (`L1`-`L4`) with
  waves, phases, and steps under stable canonical identifiers.
- **An MCP server** for Model Context Protocol clients.

See the [framework manual](./docs/framework.md) for the full tour.

> [!TIP]
> The framework favours semantic search via the core's optional sister project,
> [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag).

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
> `vaultspec-core install` handles project integration separately: it manages a block in
> your `.gitignore` and `.gitattributes`, writes pre-commit hooks, and drops an
> `.mcp.json` for Model Context Protocol clients by default.

### 3. Sync

All development paper trails live in `.vault` as markdown files. Rules, agents, and
skills are seeded from `.vaultspec` via:

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
> after a library update as the shipped agents, skills and rules might change between
> library versions.

## The pipeline at a glance

The pipeline breaks down into these steps:
`[R] Research  →  [D] Decide (ADRs)  →  [P] Plan  →  [C] Code  →  [V] Verify`. Each step
ships with its skills, agents and CLI verbs.

To start using the framework describe the work you want done in natural language:

> "Start a new vaultspec pipeline to research options for adding full-text search to the
> API."

The synced rules guide the agent through the pipeline stage by stage, writing documents
into `.vault/` as it goes: a research note, then a decision record, a plan, execution
records, and a final review. You approve each checkpoint before the agent moves on.

Invoke a stage skill directly - for example `/vaultspec-research` - to enter the
pipeline at a specific stage. See the [framework manual](./docs/framework.md) for how
each one works.

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

## Every feature leaves a paper trail

One feature tag binds a feature's whole lifecycle - research, decision, plan, execution
records, and audit - into a linked graph the CLI can trace, validate, and visualize:

<p align="center">
<img src="docs/assets/term-graph.svg" alt="vaultspec-core vault graph - a feature's document graph" width="880" />
</p>

### The vault, rendered in Obsidian

The vault is plain Markdown with wiki-links, so it opens directly in
[Obsidian](https://obsidian.md): point a vault at `.vault/` and the feature tags and
document links render as a navigable graph network, while every document's frontmatter -
tags, dates, and `related:` wiki-links - shows up as first-class properties.

<p align="center">
<img src="docs/assets/obsidian-vault.png" alt="A vaultspec vault opened in Obsidian - the document corpus as a graph network on the left, an accepted ADR with its tags, dates, and related wiki-links on the right" width="880" />
</p>

A vaultspec project's vault in Obsidian: the whole document corpus as a graph, and an
accepted ADR open beside it with its tags and related records one click away.

## A vault that audits itself

Structure only helps if it holds. `vaultspec-core vault check` runs a battery of
validators over the corpus - frontmatter, tags, links, dangling references, leftover
placeholders, plan schema, encoding - and every finding ships with its fix:

<p align="center">
<img src="docs/assets/term-check.svg" alt="vaultspec-core vault check all - validators with fix hints" width="880" />
</p>

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

## Ask your history questions

A vault is only as useful as its recall. The optional sister project
[vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) indexes both the vault and
the codebase for hybrid semantic search, so agents (and you) can ask *why* something was
decided and get the decision record back:

<p align="center">
<img src="docs/assets/term-rag.svg" alt="vaultspec-rag search - semantic recall of a decision record" width="880" />
</p>

## MCP server

We ship an MCP but the current implementation strongly favours direct CLI calls. See the
[MCP reference](./docs/MCP.md) for setup and available tools.

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
