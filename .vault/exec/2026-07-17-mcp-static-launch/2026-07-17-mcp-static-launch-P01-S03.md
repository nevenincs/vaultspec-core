---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Refresh the stale exe-form vaultspec-rag seed via rag re-enrollment and verify both MCP servers complete an initialize handshake

## Scope

- `.vaultspec/mcps`

## Description

- Refresh the stale exe-form rag seed via the uv-tool rag 0.3.0 re-enrollment
  (workspace files only, no heavy provisioning); the seeded definition is now
  the tokenized mode-neutral form.
- Declare vaultspec-rag mode dev in the committed workspace declaration so
  the render matches this repo's dev-group placement, then re-render all
  provider configs with a forced MCP sync; rag now launches module-form
  through the project venv, core unchanged.
- Verify both servers answer a real stdio initialize request.

## Outcome

Both managed MCP entries render through the mode renderer; the banned
exe-form launch is gone from every provider config; handshakes verified.

## Notes

The rag installer's ensure-mcp-extra step appended vaultspec-rag[mcp] to
core's runtime project dependencies even under --mode dev - a leaking
placement this repo forbids. Reverted; the mcp extra now rides the existing
dev-group entry instead. Recorded for the rag-side contract issue.
