---
generated: true
tags:
  - '#index'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-mcp-static-launch-P01-S01]]'
  - '[[2026-07-17-mcp-static-launch-P01-S02]]'
  - '[[2026-07-17-mcp-static-launch-P01-S03]]'
  - '[[2026-07-17-mcp-static-launch-P01-summary]]'
  - '[[2026-07-17-mcp-static-launch-P02-S04]]'
  - '[[2026-07-17-mcp-static-launch-P02-S05]]'
  - '[[2026-07-17-mcp-static-launch-P02-S06]]'
  - '[[2026-07-17-mcp-static-launch-P02-summary]]'
  - '[[2026-07-17-mcp-static-launch-P03-S07]]'
  - '[[2026-07-17-mcp-static-launch-P03-S08]]'
  - '[[2026-07-17-mcp-static-launch-P03-S09]]'
  - '[[2026-07-17-mcp-static-launch-P03-summary]]'
  - '[[2026-07-17-mcp-static-launch-adr]]'
  - '[[2026-07-17-mcp-static-launch-audit]]'
  - '[[2026-07-17-mcp-static-launch-plan]]'
  - '[[2026-07-17-mcp-static-launch-research]]'
---

# `mcp-static-launch` feature index

Auto-generated index of all documents tagged with `#mcp-static-launch`.

## Documents

### adr

- `2026-07-17-mcp-static-launch-adr` - `mcp-static-launch` adr: `the MCP launch is side-effect-free static execution` | (**status:** `accepted`)

### audit

- `2026-07-17-mcp-static-launch-audit` - `mcp-static-launch` audit: `static launch render review` | PASS after revision

### exec

- `2026-07-17-mcp-static-launch-P01-S01` - Open feature branch and draft PR referencing the venv-corruption incident and the ADR amendment
- `2026-07-17-mcp-static-launch-P01-S02` - Sweep orphaned MCP server processes holding venv DLLs and repair the venv with an explicit uv sync
- `2026-07-17-mcp-static-launch-P01-S03` - Refresh the stale exe-form vaultspec-rag seed via rag re-enrollment and verify both MCP servers complete an initialize handshake
- `2026-07-17-mcp-static-launch-P01-summary` - `mcp-static-launch` `P01` summary
- `2026-07-17-mcp-static-launch-P02-S04` - Add the no-sync guard to the dependency-mode branch of render_launch_for_mode and align its docstring with the static-execution contract
- `2026-07-17-mcp-static-launch-P02-S05` - Recognize the legacy bare uv run module launch as DEPENDENCY in the observed-shape matcher with a drift hint pointing at sync --force or install --upgrade
- `2026-07-17-mcp-static-launch-P02-S06` - Update every launch-shape assertion and add legacy-shape and no-sync render tests across the renderer, per-package sync, collector, and mode-flip suites
- `2026-07-17-mcp-static-launch-P02-summary` - `mcp-static-launch` `P02` summary
- `2026-07-17-mcp-static-launch-P03-S07` - Document the static-execution launch contract and refresh rendered-launch examples in the MCP doc and the CLI reference builtins source
- `2026-07-17-mcp-static-launch-P03-S08` - File the rag-side contract issue covering the tool-spec key and stale-seed refresh, referencing the shared launch-hygiene contract
- `2026-07-17-mcp-static-launch-P03-S09` - Run gates, dispatch code review, resolve findings, append audit entries, dogfood the refreshed .mcp.json, finalize PR
- `2026-07-17-mcp-static-launch-P03-summary` - `mcp-static-launch` `P03` summary

### plan

- `2026-07-17-mcp-static-launch-plan` - `mcp-static-launch` plan

### research

- `2026-07-17-mcp-static-launch-research` - `mcp-static-launch` research: `side-effect-free MCP launch rendering`
