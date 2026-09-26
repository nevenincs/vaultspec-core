---
tags:
  - '#exec'
  - '#env-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:aceb013015fcc5cf84d111bd967002ac8501d48d0c14baea5eed8e90c5e90f5b'
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
- `S01` `A` `src/vaultspec_core/env_values.py`
- `S01` `M` `src/vaultspec_core/__init__.py`
- `S01` `verify:` `just check-python` -> `pass`
- `S01` `verify:` `just check-type` -> `pass`
- `S01` `verify:` `pytest src/vaultspec_core/config/tests src/vaultspec_core/mcp_server/tests/test_tool_surface.py` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `M` `src/vaultspec_core/config/config.py`
- `S02` `M` `src/vaultspec_core/config/__init__.py`
- `S02` `M` `src/vaultspec_core/core/exceptions.py`
- `S02` `M` `src/vaultspec_core/config/tests/test_environment.py`
- `S02` `M` `src/vaultspec_core/config/tests/test_credential.py`
- `S02` `verify:` `just check-python` -> `pass`
- `S02` `verify:` `just check-type` -> `pass`
- `S02` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/mcp_server/tests src/vaultspec_core/triggers/tests` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/vaultspec_core/config/credential.py`
- `S03` `verify:` `just check-python` -> `pass`
- `S03` `verify:` `just check-type` -> `pass`
- `S03` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/search` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `M` `src/vaultspec_core/cli/json_output.py`
- `S04` `M` `src/vaultspec_core/cli/rendering_hints.py`
- `S04` `M` `src/vaultspec_core/cli/_trigger_trust.py`
- `S04` `M` `src/vaultspec_core/mcp_server/watchdog.py`
- `S04` `A` `src/vaultspec_core/mcp_server/kill_switch.py`
- `S04` `M` `src/vaultspec_core/mcp_server/app.py`
- `S04` `M` `src/vaultspec_core/config/config.py`
- `S04` `M` `src/vaultspec_core/console.py`
- `S04` `M` `src/vaultspec_core/vaultcore/checks/_base.py`
- `S04` `M` `src/vaultspec_core/mcp_server/tests/test_watchdog.py`
- `S04` `verify:` `just check-python` -> `pass`
- `S04` `verify:` `just check-type` -> `pass`
- `S04` `verify:` `pytest src/vaultspec_core/crossref src/vaultspec_core/config src/vaultspec_core/mcp_server/tests src/vaultspec_core/tests/cli src/vaultspec_core/vaultcore/tests` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S05` `M` `src/vaultspec_core/config/config.py`
- `S05` `M` `src/vaultspec_core/mcp_server/app.py`
- `S05` `M` `src/vaultspec_core/config/tests/test_config.py`
- `S05` `verify:` `just check-python` -> `pass`
- `S05` `verify:` `just check-type` -> `pass`
- `S05` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/mcp_server/tests` -> `pass`
- `S05` `by:` `vaultspec-high-executor`

## Notes

- `S36` Paths are in the vaultspec-rag repository, commit aeddb984 on its feat/env-parity branch.
