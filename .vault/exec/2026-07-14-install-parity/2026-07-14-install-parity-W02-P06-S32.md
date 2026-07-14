---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S32'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add upgrade-time mode inference for the vaultspec-rag package, mirroring core's \_infer_upgrade_mode detection evidence and precedence

## Scope

- `src/vaultspec_rag/commands/_install.py`

## Description

- Add `infer_rag_upgrade_mode` to `src/vaultspec_rag/commands/_mode.py`,
  mirroring core's `_infer_upgrade_mode` precedence: explicit flag wins,
  persisted rag declaration wins next, otherwise infer from deployed state.
- Route the `install --upgrade` path in `install_run` through the inference
  helper instead of the fresh-install resolver.
- Use core's `_observed_mcp_mode` collector for `vaultspec-rag` as the
  deployed-state signal (rag has no pre-commit hook), inferring dependency mode
  only when the observed launch is `uv run`-shaped and the target's
  `pyproject.toml` lists `vaultspec-rag`, tool mode otherwise.

## Outcome

A second upgrade with no flag is idempotent on the persisted mode; an explicit
flag re-modes and fires the advisory when it newly elects dependency mode; a
legacy workspace with no declaration infers its mode from its own deployed MCP
launch shape. The declaration is written before the MCP re-render, matching the
fresh-install ordering.

## Notes

Reading the observed shape through core's shared `_observed_mcp_mode` collector
keeps rag's migration and any future diagnosis in agreement on what a deployed
launch shape means, honouring the ADR's single-comparator constraint rather
than reconstructing a second matcher.
