---
tags:
  - '#exec'
  - '#discovery-fallback'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:7abf51105236317c2984afe217ef7e6240f37f7ba4643eeb725f767d2f2e12f2'
related:
  - "[[2026-09-23-discovery-fallback-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `discovery-fallback` ledger

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

- `S01` `A` `src/vaultspec_core/search/_capability.py`
- `S01` `A` `src/vaultspec_core/search/_filters.py`
- `S01` `M` `src/vaultspec_core/search/__init__.py`
- `S01` `M` `src/vaultspec_core/search/_models.py`
- `S01` `M` `src/vaultspec_core/search/_remediation.py`
- `S01` `M` `src/vaultspec_core/search/_service.py`
- `S01` `M` `src/vaultspec_core/search/_wire.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_remediation.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_service.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/collectors_companion.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S01` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S01` `M` `src/vaultspec_core/cli/vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/cli/status_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/search.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/orientation.py`
- `S01` `M` `src/vaultspec_core/mcp_server/envelope.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_search_tool.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_context_budget.py`
- `S01` `M` `pyproject.toml`
- `S01` `verify:` `just check-python check-type check-size check-complexity check-nesting check-toml framework-reference-check; pytest mcp_server search core tests config dev/guards` -> `pass`
- `S01` `by:` `opus-high`

## Notes

- `S01` MCP status does not carry the companion record: it measured +439 tool-definition chars against a ceiling the envelope ADR forbids raising; the companion reaches agents as the search next step instead
