---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S19'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the catalog module: parse the command inventory between the vaultspec:generated markers in the CLI reference at server start into an in-memory structure of verb paths, descriptions, and parameter schemas, applying the static denylist (uninstall, MCP registry mutation, index hand-authoring) at parse time (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/catalog.py`

## Description

- Add the gateway catalog module parsing the `vaultspec:generated` command-inventory marker block in the shipped CLI reference into an in-memory structure of verb paths and their curated descriptions, mirroring the proven reassemble-wrapped-bullets approach without importing the unshipped dev metrics module.
- Raise a loud `ValueError` when the marker block is absent, so an empty catalog can never be produced silently.
- Enrich each verb with its real flag schema and `--json` support by introspecting the installed Typer command tree read-only at build time, since the marker block itself carries no structured per-verb flag data; both sources ship in the same wheel and regenerate together, preserving the single-source-of-truth guarantee.
- Apply the static denylist at build time so `uninstall`, MCP-registry mutation (`spec mcps add/remove/sync`), and index hand-authoring (`vault feature index`) are excluded from entries yet remain reportable through an `is_denied` query for defense in depth; read-only `spec mcps list`/`status` stay reachable.
- Expose membership, lookup, and a deterministic token-overlap search ranking over verb paths and descriptions for the discover tool.

## Outcome

- The catalog builds 119 entries from the real installed reference (124 declared verbs minus five denylisted), each carrying accurate flags and `--json` support, with marker-absence raising loudly.

## Notes

- The marker block declares only verb paths and help prose, not flags, so `--json` support is sourced from the same Typer app the block is generated from rather than from backtick scraping; this is documented in the module and is the reason a secondary introspection exists alongside the marker parse.
