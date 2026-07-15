---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S05'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Wire selected providers and project-default MCP scopes into install, upgrade, sync, and uninstall

## Scope

- `src/vaultspec_core/core/commands.py`
- `src/vaultspec_core/core/mcps.py`

## Description

- Pass the exact fresh-install provider members into project-scope MCP reconciliation before manifest persistence.
- Route all-provider sync through the committed manifest and provider-specific sync through only the requested MCP-capable host.
- Remove recorded native MCP entries before provider directories, manifests, or ownership state are deleted.
- Report native target paths and provider-specific uninstall errors through lifecycle results.
- Treat any selected native MCP target as installed instead of using Claude's project file as a proxy.
- Make install and MCP dry-runs lock-free so previews leave no project bytes.

## Outcome

Real lifecycle probes passed Codex-only, Claude-only, Gemini-only, and all-provider fresh installs; Claude-only sync left Codex drift untouched, Codex sync repaired only Codex, Claude uninstall preserved Codex, and full uninstall removed all native targets. Install and uninstall previews were byte-stable, and a fresh install preview left an otherwise empty target directory unchanged. Ruff and type checks pass. The existing command suite reached ten passes; two assertions still expect the superseded dependency-mode default, and one pre-existing result-count assertion omits the hooks pass.

## Notes

Project scope remains the lifecycle default. Broader host scopes are not reached by root install, sync, upgrade, or uninstall unless the dedicated MCP CLI explicitly requests them in the next step.
