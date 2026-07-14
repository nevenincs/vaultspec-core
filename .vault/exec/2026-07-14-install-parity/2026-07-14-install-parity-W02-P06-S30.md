---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S30'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a mode parameter to install_run that resolves through core's resolve_install_mode with package='vaultspec-rag' and persists the result via core's write_package_declaration into the shared workspace.json

## Scope

- `src/vaultspec_rag/commands/_install.py`

## Description

- Add a `mode` parameter to `install_run` in
  `src/vaultspec_rag/commands/_install.py` and document it.
- Add `src/vaultspec_rag/commands/_mode.py` owning the rag-side seam:
  `resolve_rag_mode` (core's Q5 precedence with `package="vaultspec-rag"`),
  `persist_rag_mode` (per-package write preserving any floor and sibling
  entries), and `render_rag_mcp_entry` (scoped re-render of rag's own MCP
  entry).
- Resolve rag's mode before seeding so an impossible explicit request refuses
  loudly before any file is written.
- After core's `sync_provider`, persist rag's entry into the shared
  `.vaultspec/workspace.json` and re-render only rag's managed MCP entry at its
  own resolved mode.
- Emit core's `DEPENDENCY_LEAK_ADVISORY` onto the report warnings when
  `newly_establishes_dependency` reports this run newly elects dependency mode.

## Outcome

Rag resolves, persists, and renders its provisioning mode entirely through
core's shared `workspace_mode` machinery. A mixed configuration (core in one
mode, rag in another) is represented in one shared `packages` map with each
entry rendered at its own mode; verified end to end across all three modes plus
the core-dependency/rag-tool mixed case.

## Notes

Core's MCP sync renders every collected definition at a single sync-wide mode
(the mode resolved for `vaultspec-core`), so the sync leaves rag's entry in
core's render shape. `render_rag_mcp_entry` corrects this by re-running core's
`mcp_sync` at rag's own mode with `force_managed` scoped to `vaultspec-rag`, so
only rag's managed entry is rewritten and a sibling `vaultspec-core` entry is
left exactly as core's own sync wrote it. The re-render is gated on a real run
with core in scope, since it needs the runtime context core's sync establishes.

The advisory constant names `vaultspec-core` in its text even when emitted from
a rag install, because it is core's shared constant reused verbatim per the task
contract; a package-parameterized advisory would be a core-side change and is
flagged for the P07 review rather than forked here.
