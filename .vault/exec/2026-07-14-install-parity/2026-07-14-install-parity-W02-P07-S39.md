---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S39'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# resolve each managed MCP definition's render mode from its own declaring package so mixed-mode workspaces sync stably

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Add `_render_definition_for_sync` in `mcps.py`: a collected definition that
  names its own declaring package through `_vaultspec_mode_package` renders at
  that package's own committed render mode via `resolve_render_mode(target, package=...)`, while a definition without the key (core's own builtin) renders
  at the sync-wide mode.
- Route `collect_mcp_servers` through the new helper and add an optional
  `target` parameter used only for the per-package lookup; the raw-return
  path when `mode` is `None` is unchanged.
- Thread `target` into the three rendering callers: `mcp_status`, `mcp_sync`,
  and the doctor's registry-drift collector in `diagnosis/collectors.py`.
- Add real-filesystem, zero-mock tests in
  `tests/cli/test_mcp_per_package_sync.py`: a mixed workspace (core dependency,
  rag tool) syncs each entry in its own shape with no false SKIP; `--force`
  converges the sibling against its own tool-mode rendering rather than core's
  mode; a declaration-less legacy workspace renders both entries through the
  dependency bridge; and a core-only resync is byte-stable with zero churn.

## Outcome

Mixed-mode workspaces sync stably: `collect_mcp_servers` renders each managed
MCP entry at its own declaring package's mode, so a plain `sync` no longer emits
a spurious "differs from definition (use --force)" SKIP for a correctly
mode-rendered sibling, and `sync --force` no longer clobbers a sibling package's
entry to core's mode. Core-only and pre-`install-mode` workspaces are unchanged.
The `mcp_sync` public signature is untouched, preserving the rag 0.1.38-floor
`mcp_sync(mode=..., force_managed=...)` call. `ty` and `prek` are clean on the
changed files; the four new tests pass.

## Notes

The P06 review record this step was grounded against
(`2026-07-14-install-parity-W02-P06-S30.md`) was not present in the vault; the
acceptance criteria carried in the task assignment were used directly. One
pre-existing unrelated failure
(`tests/test_mcps.py::TestInstallSeedsMcps::test_install_creates_mcp_json_from_registry`)
reproduces on a clean stash of `origin/main` and is not caused by this change;
it shares the repo-wide `tmp_path` fixture incompatibility already tracked for
this environment.
