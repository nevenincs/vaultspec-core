<img src="https://raw.githubusercontent.com/nevenincs/vaultspec-core/main/docs/assets/logo.png" width="150" alt="Vaultspec logo">

# vaultspec-core

Decision-driven harness for coding agents, and humans.

Vaultspec is a coding harness: it implements a structured coding workflow focused on
#features, decision records and the documents grounding them. It bundles rules, agents,
skills, and tools to author the documents that describe and track a feature's
development.

The harness supports Claude Code, Codex, Gemini CLI, and Antigravity.

[<picture><source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/github/ci/nevenincs/vaultspec-core.svg?workflow=main-health.yml&amp;branch=main&amp;label=ci&amp;variant=secondary&amp;size=xs&amp;mode=dark"><img alt="CI status of main" src="https://shieldcn.dev/github/ci/nevenincs/vaultspec-core.svg?workflow=main-health.yml&amp;branch=main&amp;label=ci&amp;variant=secondary&amp;size=xs&amp;mode=light"></picture>](https://github.com/nevenincs/vaultspec-core/actions/workflows/main-health.yml)
[<picture><source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/pypi/v/vaultspec-core.svg?label=pypi&amp;variant=secondary&amp;size=xs&amp;mode=dark"><img alt="PyPI version" src="https://shieldcn.dev/pypi/v/vaultspec-core.svg?label=pypi&amp;variant=secondary&amp;size=xs&amp;mode=light"></picture>](https://pypi.org/project/vaultspec-core/)
[<picture><source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/badge/python-3.13%20%7C%203.14.svg?logo=python&amp;variant=secondary&amp;size=xs&amp;mode=dark"><img alt="Supported Python versions" src="https://shieldcn.dev/badge/python-3.13%20%7C%203.14.svg?logo=python&amp;variant=secondary&amp;size=xs&amp;mode=light"></picture>](https://www.python.org/downloads/)
[<picture><source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/github/license/nevenincs/vaultspec-core.svg?label=license&amp;variant=secondary&amp;size=xs&amp;mode=dark"><img alt="License" src="https://shieldcn.dev/github/license/nevenincs/vaultspec-core.svg?label=license&amp;variant=secondary&amp;size=xs&amp;mode=light"></picture>](https://github.com/nevenincs/vaultspec-core/blob/main/LICENSE)

[Install](#install) · [Start a feature](#start-a-feature) ·
[Documentation](#documentation) · [Optional services](#optional-services)

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run this
from your repository root:

```bash
uvx vaultspec-core install
```

Vaultspec supports Python 3.13 and 3.14. uv downloads a supported interpreter if needed.

The installer writes rules, skills, and agent configuration into your project. For
Claude Code, Codex, and Antigravity it also configures a Model Context Protocol (MCP)
server so the agent can call the tools; Gemini CLI calls them through the CLI.

Workflow documents live in `.vault/`; the policy lives in `.vaultspec/`. Commit both so
teammates share the records and rules. Installation also manages ignore rules for local
state and, unless you pass `--skip precommit`, writes a pre-commit configuration.
Activating commit hooks is a
[separate choice](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md#configure-project-integrations).

To check the result, run:

```bash
uvx vaultspec-core doctor
```

It reports installation and record problems;
[checking a workspace](https://github.com/nevenincs/vaultspec-core/blob/main/docs/verification.md)
explains how to repair them.

Keep the `uvx` prefix when running commands yourself. For persistent or project-local
installation, see
[installation options](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md#installation-options).

[Scoop and Homebrew](https://github.com/nevenincs/vaultspec-core/blob/main/docs/channels.md)
provide binaries for Windows x86-64, Linux, and Apple silicon Macs. Each carries its own
interpreter, Vaultspec and every dependency, so it needs no separate Python install and
no network. A binary puts `vaultspec-core` on your PATH: run the commands in this README
without the `uvx` prefix. On an Intel Mac, install with uv.

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
[workflow guide](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md#choose-the-route-for-your-task)
explains how to choose a route, approve work, and continue across sessions.

## Documentation

- [Documentation index](https://github.com/nevenincs/vaultspec-core/blob/main/docs/README.md):
  choose a guide for your task.
- [Framework manual](https://github.com/nevenincs/vaultspec-core/blob/main/docs/framework.md):
  run the workflow and customize its rules.
- [Document syntax](https://github.com/nevenincs/vaultspec-core/blob/main/docs/syntax.md):
  edit prose and manage document structure.
- [Checking a workspace](https://github.com/nevenincs/vaultspec-core/blob/main/docs/verification.md):
  check the setup and repair errors.
- [Reviewing an implementation](https://github.com/nevenincs/vaultspec-core/blob/main/docs/correctness.md):
  review a change against its scope and test evidence.
- [CLI reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md) and
  [MCP reference](https://github.com/nevenincs/vaultspec-core/blob/main/docs/MCP.md):
  commands, tools, and configuration.

## Optional services

Open `.vault/` in [Obsidian](https://obsidian.md) to browse its linked documents. The
optional [vaultspec-rag](https://github.com/nevenincs/vaultspec-rag) package adds
semantic search across the vault and your code.

Hosted search and ranking are optional. Set `VAULTSPEC_CORE_TYPESAFE_API_KEY` in the
environment, or import it by name with
`uvx vaultspec-core install --env VAULTSPEC_CORE_TYPESAFE_API_KEY` (add `--upgrade` for
an existing installation).
[Local provisioning](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md#local-environment-provisioning)
lists every place the key can come from. The key enables:

- [`vaultspec-core vault search`](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md#vaultspec-core-vault-search)
  (MCP: `search`): answers vault questions with a supporting passage.
- [`vaultspec-core vault adr crossref`](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md#vaultspec-core-vault-adr-crossref)
  (MCP: `crossref`): suggests related ADRs and flags possible conflicts for the author
  to reconcile.
- [`vaultspec-core project context`](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md#vaultspec-core-project-context)
  and
  [`vaultspec-core review context`](https://github.com/nevenincs/vaultspec-core/blob/main/docs/CLI.md#vaultspec-core-review-context):
  rank coordination work and review evidence. Pass `--no-hosted` to skip the hosted
  request.

These calls send data to the TypeSafe API: vault text for search and cross-referencing,
the objective and up to twelve shortlisted work-item summaries for project context, and
the review objective, bounded diff and candidate passages for review context. Without a
key, they send nothing. Search and cross-referencing then name a discovery fallback: a
vaultspec-rag vault search when the workspace provisions vaultspec-rag, otherwise
`vaultspec-core vault list`, plus grep for search. The workflow can continue with that
evidence. Project and review context order their results from local signals. Code search
is always vaultspec-rag's job.

## Support and license

vaultspec-core is in beta. Report bugs, ask questions, or propose changes on the
[issue tracker](https://github.com/nevenincs/vaultspec-core/issues). For contributions
and releases, see
[maintainer documentation](https://github.com/nevenincs/vaultspec-core/blob/main/docs/README.md#for-maintainers).

Released under the
[MIT License](https://github.com/nevenincs/vaultspec-core/blob/main/LICENSE).
