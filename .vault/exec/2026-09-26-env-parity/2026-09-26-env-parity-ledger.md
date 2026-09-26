---
tags:
  - '#exec'
  - '#env-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:df2239d1fab075dfd7b71b1ba10df5b6eb4b1be18ca1dad08c08390976852965'
related:
  - "[[2026-09-26-env-parity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `env-parity` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S13` `M` `.vault/adr/2026-02-16-environment-variable-adr.md`
- `S13` `M` `.vault/adr/2026-02-19-workspace-path-decoupling-adr.md`
- `S13` `M` `.vault/adr/2026-05-17-cli-spec-edit-safety-adr.md`
- `S13` `M` `.vault/adr/2026-07-13-install-mode-adr.md`
- `S13` `M` `.vault/adr/2026-07-14-install-parity-adr.md`
- `S13` `M` `.vault/adr/2026-09-23-typesafe-search-adr.md`
- `S13` `verify:` `vaultspec-core vault check all` -> `pass`
- `S13` `by:` `orchestrator`
- `S36` `M` `.vault/adr/2026-09-21-typesafe-classifier-adr.md`
- `S36` `M` `.vault/adr/2026-04-04-test-and-paths-adr.md`
- `S36` `M` `.vault/adr/2026-04-12-vaultspec-rag-install-adr.md`
- `S36` `M` `.vault/adr/2026-06-18-mcp-service-client-adr.md`
- `S36` `M` `.vault/adr/2026-07-13-index-drift-hardening-adr.md`
- `S36` `verify:` `vaultspec-core vault check all` -> `pass`
- `S36` `by:` `vaultspec-docs-curator`

## Notes

- `S36` Paths are in the vaultspec-rag repository, commit aeddb984 on its feat/env-parity branch.
