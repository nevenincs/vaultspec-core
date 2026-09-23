---
tags:
  - '#plan'
  - '#typesafe-search'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-typesafe-search-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:7eaf8386e96671ac50800988f4661edcd5e0e8c33ead655cd23d61dd1ca69f7c'
---

# `typesafe-search` plan

Hosted vault search on TypeSafe Jev: ranked records with verbatim excerpts, rag as the agent-level fallback.

## Description

Approved 2026-09-23. The user authorised delivery of the feature ("carte blanche to
implement and deliver the TypeSafe integration and ranking, filtering search feature")
and waived all approval gates for autonomous delivery.

Implement hosted vault search as decided in `2026-09-23-typesafe-search-adr`, whose
evidence is `2026-09-23-typesafe-search-research`. The ADR governs every Step; its
amendment notes on `2026-07-09-mcp-tool-schema-adr` and `2026-08-01-mcp-read-only-adr`
cover S06. `2026-08-26-rag-search-exposure-adr` constrains S03 to S08 unchanged: core
never calls rag. `2026-08-23-envelope-optimization-adr` bounds the S06 and S07 replies.
`2026-02-16-environment-variable-adr` governs S03.

Standing user mandate for every Step: no duplicated or fragmented code. Enums, types,
helpers and declarations are reused from their canonical homes (`DocType`,
`InstallMode`, `CONFIG_REGISTRY`, `git_blob_oid`, `apply_window`, the MCP envelope).
Fragmented duplicates the feature touches are rehomed. S01 does this for the five
fence regexes and two section scanners, before the search corpus builds on them.

## Steps

- [x] `S01` - Rehome fence-aware markdown scanning (fences, headings, sections, paragraph blocks) into one canonical vaultcore module and migrate the existing fence, heading and section scanners onto it; `src/vaultspec_core/vaultcore/markdown.py, src/vaultspec_core/core/tags.py, src/vaultspec_core/vaultcore/checks/, src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `S02` - Declare the search package contract: result models, question set and public exports; `src/vaultspec_core/search/__init__.py, src/vaultspec_core/search/_models.py, src/vaultspec_core/search/_questions.py`.
- [x] `S03` - Register the hosted-search key as a secret config variable and resolve it from the process environment, then the workspace .env in DEPENDENCY or DEV mode; `src/vaultspec_core/config/config.py, src/vaultspec_core/search/_credential.py, .env.example`.
- [x] `S04` - Implement the stdlib Jev transport: pooled HTTPS, bounded concurrency, deadline, retry, failure taxonomy with content rejection, sanitisation, size preflight and answer validation; `src/vaultspec_core/search/_transport.py, src/vaultspec_core/search/tests/`.
- [x] `S05` - Implement the vault corpus, lexical ranking, two-stage engine and the search_vault service; `src/vaultspec_core/search/_corpus.py, src/vaultspec_core/search/_lexical.py, src/vaultspec_core/search/_engine.py, src/vaultspec_core/search/_service.py`.
- [ ] `S06` - Add the MCP search tool to the normal and read-only surfaces and the hosted-search field to status; `src/vaultspec_core/mcp_server/tools/search.py, src/vaultspec_core/mcp_server/app.py, src/vaultspec_core/mcp_server/tools/orientation.py, docs/MCP.md`.
- [ ] `S07` - Add the vault search CLI verb and the CLI status row, and regenerate the CLI and MCP references; `src/vaultspec_core/cli/vault_search_cmd.py, src/vaultspec_core/cli/status_cmd.py, docs/CLI.md, src/vaultspec_core/builtins/reference/cli.md`.
- [ ] `S08` - Route discovery guidance to core search when configured and to vaultspec-rag otherwise; `src/vaultspec_core/core/discovery_guidance.py, src/vaultspec_core/builtins/`.
- [ ] `S09` - Add the deselected typesafe marker and a live test over a synthetic vault, then verify against this vault; `pyproject.toml, dev/toolchain.py, src/vaultspec_core/search/tests/test_live.py`.
- [x] `S10` - Rehome the remaining fence, heading and frontmatter duplicates onto the canonical scanner and parser, and bump the graph cache schema for the changed title reading; `src/vaultspec_core/vaultcore/links.py, src/vaultspec_core/plan/parser.py, src/vaultspec_core/plan/checks/heading_level_check.py, src/vaultspec_core/vaultcore/exec_fold.py, src/vaultspec_core/mcp_server/tools/documents.py, src/vaultspec_core/graph/cache.py`.
- [ ] `S11` - Move the byte-preserving write-path frontmatter splitters onto the canonical splitter, with YAML-block offsets and lone-CR support, keeping body_hash digests byte-identical; `src/vaultspec_core/vaultcore/parser.py, src/vaultspec_core/vaultcore/body_hash.py, src/vaultspec_core/vaultcore/models.py, src/vaultspec_core/vaultcore/hydration.py, src/vaultspec_core/vaultcore/exec_recovery.py, src/vaultspec_core/vaultcore/rename_ops.py, src/vaultspec_core/vaultcore/query_rename.py, src/vaultspec_core/vaultcore/related_surgery.py`.

## Parallelization

Delegated lanes write only their assigned files and run only their own new or
changed tests plus ruff and ty on those files. The orchestrator owns commits, the
whole-repo gates, reference regeneration and the full test run, so no check is
repeated across lanes.

- Wave 1, in parallel: S01 (markdown lane) and S03 plus S04 (transport lane). S02 is
  written by the orchestrator before either starts.
- Wave 2: S05 (engine lane). It depends on the S01 scanner, the S02 contract and the
  S03 and S04 client and credential API.
- Wave 3, in parallel: S06 (MCP lane) and S07 plus S08 (CLI and guidance lane). Both
  depend on S05's `search_vault`. The orchestrator regenerates the shared references
  after both land.
- S09 and the integrated review run last, by the orchestrator.

## Verification

- `just check-python`, `check-type`, `type-strict`, `check-complexity`,
  `check-nesting`, `check-size`, `check-markdown` and `check-links` pass, and deptry
  reports no new dependency.
- The broad test lane passes with no network and no key, including the updated
  tool-surface, context-budget and reference-drift guards.
- The `typesafe`-marked live test passes with a key. A run over this vault reproduces
  the research findings: the right record first on labelled queries, verbatim excerpts
  at the reported lines, and abstention on unanswerable queries.
- With no key, `search` returns `not_configured` and names the rag invocation, and the
  MCP tool list is unchanged across key states.
- The key never appears in output, logs or errors, including under failure.
- An integrated review against the ADR passes, and CI is green on the pull request.
