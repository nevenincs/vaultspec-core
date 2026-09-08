<img src="docs/assets/logo.png" width="150" alt="Vaultspec logo">

# vaultspec-core

Decision-driven harness for coding agents, and humans.

Vaultspec is a coding harness: it implements a structured coding workflow focused on
#features, decision records and the documents grounding them. It bundles rules, agents,
skills, and tools to author the documents that describe and track a feature's
development.

The harness supports Claude Code, Codex, Gemini CLI, and Antigravity.

[![build](https://img.shields.io/github/actions/workflow/status/nevenincs/vaultspec-core/ci.yml?branch=main&style=flat&label=build&logo=githubactions&logoColor=white&labelColor=24292f&color=57606a)](https://github.com/nevenincs/vaultspec-core/actions/workflows/ci.yml)
[![release](https://img.shields.io/pypi/v/vaultspec-core?style=flat&label=release&logo=pypi&logoColor=white&labelColor=24292f&color=57606a)](https://pypi.org/project/vaultspec-core/)
[![runtime](https://img.shields.io/badge/runtime-Python%203.13%20%7C%203.14-57606a?style=flat&logo=python&logoColor=white&labelColor=24292f)](https://www.python.org/downloads/)
[![license](https://img.shields.io/github/license/nevenincs/vaultspec-core?style=flat&label=license&logo=opensourceinitiative&logoColor=white&labelColor=24292f&color=57606a)](https://github.com/nevenincs/vaultspec-core/blob/main/LICENSE)

[Install](#install) · [Start a feature](#start-a-feature) ·
[Documentation](#documentation)

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run this
from your repository root:

```bash
uvx vaultspec-core install
```

Vaultspec supports Python 3.13 and 3.14. uv downloads a supported interpreter if needed.

The installer writes rules, skills, and agent configuration into your project and
configures a Model Context Protocol (MCP) server so your agent can call the tools.

Workflow documents live in `.vault/`; the policy lives in `.vaultspec/`. Commit both so
teammates share the records and rules. Installation also manages ignore rules for local
state and writes pre-commit configuration. Activating commit hooks is a
[separate choice](docs/framework.md#configure-project-integrations).

Keep the `uvx` prefix when running commands yourself. For persistent or project-local
installation, see [installation options](docs/framework.md#installation-options).
[Homebrew and Scoop](docs/channels.md) provide binaries that need no separate Python
install and no network: each one carries its own interpreter, Vaultspec and every
dependency.

## Start a feature

Open your repository in your coding agent and describe the work:

> Add full-text search to the API. Use the feature tag search-api. Check existing
> decisions first, and show me any new decision and implementation plan for approval.

The agent uses the parts of the workflow the task needs:

- Routine changes can proceed directly within your request.
- A costly-to-reverse choice needs evidence and an approved architecture decision record
  (ADR). Reuse an existing accepted ADR when it already covers the work.
- Work that needs durable sequencing or handoff uses a plan, with or without a new ADR.
  The agent implements and verifies each Step, logs the changes, and reviews the
  integrated result.

Rules guide the agent's decisions; tools maintain document structure and progress.
Record checks complement tests and review, but do not prove the code is correct.
Approval covers the agreed scope, including ordinary in-scope corrections; new choices
outside that authorization need your input.

A feature tag groups the work's records. To see recorded progress:

```bash
uvx vaultspec-core status search-api
```

For planned work, ask the agent to resume the feature from its next open Step. The
[workflow guide](docs/framework.md#begin-a-pipeline) explains how to choose a route,
approve work, and continue across sessions.

## Documentation

- [Documentation index](docs/README.md): choose a guide for your task.
- [Framework manual](docs/framework.md): run the workflow and customize its rules.
- [Document syntax](docs/syntax.md): edit prose and manage document structure.
- [Verifying a workspace](docs/verification.md): check the setup and repair errors.
- [CLI reference](docs/CLI.md) and [MCP reference](docs/MCP.md): commands, tools, and
  configuration.

Open `.vault/` in [Obsidian](https://obsidian.md) to browse its linked documents. The
optional [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) package adds
semantic search across the vault and your code.

## Support and license

vaultspec-core is in beta. Report bugs, ask questions, or propose changes on the
[issue tracker](https://github.com/nevenincs/vaultspec-core/issues). For contributions
and releases, see [maintainer documentation](docs/README.md#for-maintainers).

Released under the [MIT License](LICENSE).
