---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S04'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Export the stable package-aware companion reconcile API

## Scope

- `src/vaultspec_core/core/__init__.py`
- `src/vaultspec_core/core/mcps.py`

## Description

- Export typed provider, scope, format, target, and install-mode contracts from the public Core package.
- Export native target resolution, package-aware launch rendering, sync, status, and uninstall functions.
- Preserve the single canonical definition renderer for Core and companion packages.

## Outcome

A consumer importing only `vaultspec_core.core` reconciled Claude and Codex in a fresh workspace without ambient context, inspected aggregate native status, resolved typed targets, verified package-aware launch rendering, and uninstalled both providers with per-tool outcomes. Ruff and type checks pass.

## Notes

`provider="all"` reads the persisted enrolled-provider manifest during ordinary lifecycle calls. Fresh pre-manifest callers pass the exact `enrolled` provider members explicitly, preventing accidental host selection.
