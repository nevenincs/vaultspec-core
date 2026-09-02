<div align="center">

<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/logo.png" alt="vaultspec-core logo" width="150" />

# vaultspec-core

**Make your AI coding assistant write down what it decided, and why.**

[![install](https://img.shields.io/badge/install-uvx%20vaultspec--core%20install-2E6B45?style=for-the-badge&logo=uv&logoColor=white&labelColor=1b1a16)](#install)
[![build](https://img.shields.io/github/actions/workflow/status/nevenincs/vaultspec-core/ci.yml?branch=main&style=for-the-badge&label=build&logo=githubactions&logoColor=white&labelColor=1b1a16)](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml)
[![release](https://img.shields.io/pypi/v/vaultspec-core?style=for-the-badge&label=release&logo=pypi&logoColor=white&labelColor=1b1a16&color=8A72B5)](https://pypi.org/project/vaultspec-core/)
[![runtime](https://img.shields.io/badge/runtime-Python%203.13%20%7C%203.14-3F9AA6?style=for-the-badge&logo=python&logoColor=white&labelColor=1b1a16)](https://www.python.org/downloads/)
[![license](https://img.shields.io/github/license/nevenincs/vaultspec-core?style=for-the-badge&label=license&logo=opensourceinitiative&logoColor=white&labelColor=1b1a16&color=B3823C)](https://github.com/nevenincs/vaultspec-core/blob/main/LICENSE)

[Install](#install) · [First run](#your-first-feature) · [Documentation](#documentation)
· [Family](#the-vaultspec-family) · [Support](#status-help-and-license)

</div>

## What this is

vaultspec-core is a command-line tool for projects where an AI assistant writes some of
the code. It works with Claude Code, Codex, Gemini CLI, and Antigravity.

Installing it puts a set of rules and slash-commands into your repository. Those push
the assistant through five stages for any piece of work: research the problem, record
the decision, write a plan, execute the plan, review the result. Each stage is saved as
a Markdown file under a `.vault/` folder that you commit alongside your code.

The point is what happens next session. The assistant reads those files before it writes
anything, so it does not re-argue decisions you already settled or rebuild something you
deliberately rejected. The files are plain Markdown, so you can read, grep, and review
them like any other source file.

The CLI is the part that keeps those files trustworthy. It creates every document from a
template and validates the whole set on demand, so filenames, metadata, and
cross-references stay consistent instead of drifting as the assistant writes more of
them.

<p align="center">
<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/demo.gif" alt="Provisioning a project, scaffolding research, ADR, and plan, then checking and graphing the vault" width="880" />
</p>

## What you get

Every document is created by the CLI, never hand-written. This is a research note, the
first document of a feature, exactly as the tool writes it:

```markdown
---
tags:
  - '#research'
  - '#search-api'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9052b61859eb83c17b4a20d8792f96456c7b2d5a340b6a12ed92add4dabc88c1'
related: []
---
```

The `tags` bind the document to one feature. `related` links it to the other documents
of that feature, so a decision, its plan, and its review form a graph the CLI can
validate and draw. `body_hash` records what the document said when it was last stamped,
which is how an unrecorded edit becomes detectable.

## Requirements

- A git repository. Run the install from inside one.
- [uv](https://docs.astral.sh/uv/). You probably do not have it: a stock macOS machine
  has neither `uv` nor Homebrew, and its system Python is 3.9, below what this package
  supports.

Install uv first:

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

uv fetches a suitable Python itself, so you do not install one separately. The supported
versions are 3.13 and 3.14.

## Install

From the root of your git repository:

```bash
uvx vaultspec-core install
```

That writes the rules, skills, and agent definitions, enables them for every AI client
it finds, and sets up the Model Context Protocol server:

```
Installed vaultspec
  Target /path/to/your/project
  Synced 3 rules, 10 skills, 10 agents
  Enabled claude, gemini, antigravity, codex
  Installed MCP server

Next action:
  Framework installed. Start research on your first feature
    vaultspec-core vault add research --feature {feature_tag}
```

It also manages a block in your `.gitignore` and `.gitattributes`, writes pre-commit
hooks, and drops an `.mcp.json`. The rules and `.mcp.json` are committed so teammates
inherit the same setup; local by-products are not.

Install chooses how the hooks and the MCP server launch, defaulting to running
vaultspec-core through `uvx` so it never joins your dependency set. Override with
`--mode dependency` or `--mode dev` if you would rather it resolve through your project
environment. The
[CLI reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md)
covers the modes and when each applies.

After upgrading the package, re-run `vaultspec-core install --upgrade`, because the
shipped rules, skills, and agents change between versions.

## Your first feature

Two ways in. Either scaffold the first document yourself:

```bash
vaultspec-core vault add research --feature search-api
```

```
Created: .vault/research/2026-09-02-search-api-research.md

Next action:
  Define an Architecture Decision Record (ADR) for your research
    vaultspec-core vault add adr --feature search-api --related 2026-09-02-search-api-research
```

Each command tells you the next one, so you can follow the chain without memorising the
pipeline.

Or, more usually, say what you want in your AI client and let it drive:

> "Start a new vaultspec pipeline to research options for adding full-text search to the
> API."

The installed rules walk the assistant through the stages, writing documents as it goes
and pausing at each checkpoint for your approval.

To enter at a specific stage, type a slash-command **into your AI client**, not into a
shell: `/vaultspec-research`, `/vaultspec-adr`, and so on.

## The pipeline

`Research → Decide → Plan → Execute → Verify`. The Decide stage produces an Architecture
Decision Record (ADR), a short document stating what was chosen and what it rules out.
Research has a parallel entry point, Reference, which grounds the work in code that
already exists; a feature can start from either or both.

Ten skills install with the tool. Six drive the pipeline stages, and four cover upkeep:

| When you want to                              | Skill                       |
| :-------------------------------------------- | :-------------------------- |
| Explore a problem and weigh options           | `/vaultspec-research`       |
| Ground the work in the existing codebase      | `/vaultspec-code-research`  |
| Record the decision and its consequences      | `/vaultspec-adr`            |
| Turn the decision into an implementation plan | `/vaultspec-write`          |
| Work through the plan, step by step           | `/vaultspec-execute`        |
| Audit the finished work by severity           | `/vaultspec-code-review`    |
| Repair vault links, metadata, and naming      | `/vaultspec-curate`         |
| Draft user-facing documentation               | `/vaultspec-documentation`  |
| Coordinate work across parallel agents        | `/vaultspec-team`           |
| Track issues, milestones, and releases        | `/vaultspec-projectmanager` |

An eleventh, `/vaultspec-rag-discovery`, installs only when the optional
[vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) is present. It finds code,
or the decision behind it, by meaning rather than by keyword.

Plans carry more structure than a flat list when the work needs it, sized from a short
checklist up to a multi-stage epic. The
[framework manual](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md)
covers the stages, the skills, and the plan structure in full.

## Working with the vault

Four commands cover everyday use:

```bash
# Create a document from a template
vaultspec-core vault add research --feature search-api

# List what exists for a feature
vaultspec-core vault list --feature search-api

# Validate metadata, links, and cross-references (--fix repairs the safe ones)
vaultspec-core vault check all --fix

# Draw a feature's document graph
vaultspec-core vault graph --feature search-api
```

`vault check` runs twenty validators over the corpus, covering metadata, tags, links,
dangling references, leftover template placeholders, plan schema, and encoding. Every
finding carries a fix hint, and `--fix` applies the safe ones:

<p align="center">
<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/term-check.svg" alt="vaultspec-core vault check all, showing validators with fix hints" width="880" />
</p>

`vaultspec-core status` shows which plans are in flight and what changed recently:

<p align="center">
<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/term-status.svg" alt="vaultspec-core status, live output from this repository's own vault" width="880" />
</p>

Document bodies are yours to edit. Filenames, metadata, and plan structure are not:
those come from the CLI, which is what lets it validate them later.

## Optional extras

### Read the vault in Obsidian

The vault is plain Markdown with wiki-links, so point [Obsidian](https://obsidian.md) at
`.vault/` and the whole corpus renders as a navigable graph, with each document's tags,
dates, and links as first-class properties.

<p align="center">
<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/obsidian-vault.png" alt="A vaultspec vault opened in Obsidian, showing the document corpus as a graph beside an accepted ADR" width="880" />
</p>

### Search the vault by meaning

[vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) is a separate package that
indexes the vault and your source code for semantic search, so you can ask why something
was decided and get the decision record back rather than a keyword match:

<p align="center">
<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/term-rag.svg" alt="vaultspec-rag search, recalling a decision record" width="880" />
</p>

### The MCP server

`vaultspec-core install` sets up a Model Context Protocol server by default, which lets
an MCP-capable client call the CLI's operations directly instead of shelling out. Seven
tools cover everyday work (`find`, `create`, `edit`, `status`, `check`, `plan_progress`,
`plan_edit`), and a `discover`/`invoke` pair reaches the rest of the CLI. If the server
is running the assistant uses it; otherwise it runs the same operations through the CLI.
See the
[MCP reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/MCP.md).

## Other ways to install

Choose one of these instead of `uvx` if it suits you better:

```bash
# A local tool, if you want the command available outside this project
uv tool install vaultspec-core

# A project dependency, if you want it pinned in pyproject.toml
uv add vaultspec-core
```

After `uv add`, bootstrap from inside your environment with
`uv run vaultspec-core install`.

If you would rather not have a Python toolchain on the machine at all, install the
standalone binaries:

```powershell
# Windows, via Scoop
scoop bucket add nevenincs https://github.com/nevenincs/homebrew-tap
scoop install vaultspec-core
```

```bash
# macOS and Linux, via Homebrew
brew tap nevenincs/tap https://github.com/nevenincs/homebrew-tap
brew install vaultspec-core
```

The `homebrew-tap` repository is the channel root for the whole account and serves Scoop
as well, so you add it once and it carries every vaultspec product. Both commands put
`vaultspec-core` and `vaultspec-mcp` on your `PATH`. The first run downloads the Python
runtime it needs, so it requires a network connection once. Homebrew covers macOS on
Apple Silicon and Linux on x86-64; Intel macOS and Linux arm64 are not built, and
[docs/channels.md](https://github.com/nevenincs/vaultspec-core/blob/main/docs/channels.md)
says why.

## The vaultspec family

All four are in beta.

| Project                                                                 | Role                                                |
| ----------------------------------------------------------------------- | --------------------------------------------------- |
| vaultspec-core                                                          | This package: the pipeline, the vault, and the CLI. |
| [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag)             | Semantic search over the vault and your code.       |
| [vaultspec-dashboard](https://github.com/nevenincs/vaultspec-dashboard) | A user interface for the whole thing.               |
| [vaultspec-a2a](https://github.com/nevenincs/vaultspec-a2a)             | Headless agent-to-agent orchestration.              |

## Documentation

| Guide                                                                                       | What it covers                                                |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| [Framework manual](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md) | The stages, skills, agents, plan structure, and customization |
| [CLI reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md)          | Every command, flag, and option                               |
| [MCP reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/MCP.md)          | The MCP server tools, setup, and configuration                |

## Status, help, and license

vaultspec-core is in beta and actively developed. The version badge shows the current
release. File bugs and questions on the
[issue tracker](https://github.com/nevenincs/vaultspec-core/issues); bug reports,
feature ideas, and pull requests are all welcome. Released under the
[MIT License](https://github.com/nevenincs/vaultspec-core/blob/main/LICENSE).

## For contributors

Releases run on [release-please](https://github.com/googleapis/release-please). Merging
conventional commits (`feat:`, `fix:`, `feat!:`) to `main` keeps an open Release PR with
the next version and changelog. Merging that PR tags a GitHub Release, which triggers
the publish workflow: it builds the package, runs smoke tests against the built wheel
and sdist, and publishes to PyPI over OIDC trusted publishing, so no long-lived PyPI
token is stored in the repository.
