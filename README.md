# vaultspec-core

[![Continuous integration](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml/badge.svg)](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/vaultspec-core.svg)](https://pypi.org/project/vaultspec-core/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-vaultspec--mcp-informational)](./docs/MCP.md)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

---

**Vaultspec is a spec-driven harness for coding agents (and us, the humans).**

---

Vaultspec guides agents through a
```Research → Decide → Plan → Code → Verify``` pipeline not dissimilar to other spec driven
frameworks (Superpowerers!)

All work leaves a papertrail in the project's `.vault`. Documents are bound together by tags,
and references. Together, they represents the project's decision and execution history.

> [!TIP]
> Point Obsidian at the `.vault` for browsing and graphing document.


## What is included?

`vaultspec-core` implements natural language codification of the workflow. It ships rules,
skills and agents, and a CLI to manage vault health, work tracking, and and the shipped harness. See 
[framework manual](./docs/framework.md) for more info.

> [!TIP]
> The framework favours semantic search via the core's sister project,
> [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) 

## The pipeline at a glance

```
[R] Research  →  [D] Decide (ADR)  →  [P] Plan  →  [E] Code (Exec)  →  [V] Review (Code Review, Audit)
```

| Stage    | What it produces                                       | You                                            |
| -------- | ------------------------------------------------------ | ---------------------------------------------- |
| Research | Options and findings in `.vault/research/`             | Review and approve the findings                |
| Decide   | An Architecture Decision Record (ADR) in `.vault/adr/` | Approve the decision                           |
| Plan     | An implementation plan in `.vault/plan/`               | Review and approve the plan                    |
| Execute  | Execution records in `.vault/exec/`                    | Stay available while the agent works each step |
| Review   | A review and audit report in `.vault/audit/`           | Read the report and decide if the work ships   |


## Getting started

### 1. Install

For the quickest, dependency-free project bootstrap, run:

```bash
uvx vaultspec-core install
```

Or use it as a tool or dependency:

```
# You can add it as a local tool
uv tool install vaultspec-core

# Or a project dependency
uv add vaultspec-core
```

### 2. Bootstrap

```bash
uv run --no-sync vaultspec-core install [--upgrade]
```

This sets up the framework for the supported coding agents: Claude, Codex, Gemini, and
Antigravity. It also creates two folders in your project: `.vault/` for your documents
and `.vaultspec/` for the framework configuration. Pass `--upgrade` to re-seed the
bundled builtins.

> [!NOTE]
> `uv add` writes vaultspec-core into your `pyproject.toml`.
> `vaultspec-core install` handles the rest of the project integration separately: it
> manages a block in your `.gitignore` and `.gitattributes`, writes pre-commit hooks,
> and drops an `.mcp.json` for Model Context Protocol clients by deafult.

### Drive your first feature

Open your coding agent - such as Claude Code, Codex, or Gemini - in the project root,
then describe the work you want done in natural language:

> "Research options for adding full-text search to the API."

The synced rules guide the agent through the pipeline stage by stage, writing documents
into `.vault/` as it goes: a research note, then a decision record, a plan, execution
records, and a final review. You approve each checkpoint before the agent moves on.

Invoke a stage skill directly - for example `/vaultspec-research` - to enter the
pipeline at a specific stage. See the [bundled skills](#skills) for the full set, or the
[framework manual](./docs/framework.md) for how each one works.

## What vaultspec-core contains

vaultspec-core bundles everything needed to run the spec-driven pipeline: a command-line
tool, a set of skills, agent personas, shared policy rules, and an MCP server.

### The CLI

`vaultspec-core` is the runtime that ties the framework together. It installs and syncs
the framework configuration, validates vault documents, and manages plans through their
full lifecycle - from authoring steps to checking completion. See the
[CLI reference](./docs/CLI.md) for the full command inventory.

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

### Agents

Agents are the personas that execution delegates to. Each has a defined role and a
declared tool-access level: some write files and run commands, others only read and
return findings. Execution dispatches independent plan steps to several agents in
parallel, which keeps long plans moving instead of blocking on each step in sequence.

### Rules and system prompts

The `.vaultspec/` directory holds the policy that shapes how agents behave: rules, skill
definitions, agent declarations, and system prompt fragments. This configuration is
team-shared by default and syncs into each provider on demand. Use `vaultspec-core spec`
to inspect, update, and propagate changes across the workspace.

### MCP server

The MCP server exposes vault discovery and document creation over the Model Context
Protocol (MCP) to clients such as Claude Code via stdio. It's an alternative to
file-based sync for environments where a live connection to the vault is more convenient
than reading files directly. See the [MCP reference](./docs/MCP.md) for setup and
available tools.

## Working in the vault

### Where work lives

`.vault/` holds every document your features produce, organized by type: `research/`,
`reference/`, `adr/`, `plan/`, `exec/`, `audit/`, and an auto-generated `index/`. Each
document carries a feature tag, and wiki-links bind a feature's documents together
across its lifecycle. Everything is Markdown committed to git, so the record travels
with the code.

> **Tip:** The vault is plain Markdown with wiki-links, so it opens directly in
> [Obsidian](https://obsidian.md). Point an Obsidian vault at `.vault/` and its feature
> tags and document links render as a navigable graph network.

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
