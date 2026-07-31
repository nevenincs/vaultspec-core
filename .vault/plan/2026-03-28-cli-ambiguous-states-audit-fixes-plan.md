---
tags:
  - '#plan'
  - '#cli-ambiguous-states'
date: '2026-03-28'
modified: '2026-07-31'
body_hash: 'sha256:1137067d1d9c274dd68d5e6e3aeb5408a1960f0f7061311b0b86631c9c85e095'
tier: L2
related:
  - '[[2026-03-27-cli-ambiguous-states-audit]]'
  - '[[2026-03-27-cli-ambiguous-states-resolver-adr]]'
  - '[[2026-03-27-cli-ambiguous-states-plan]]'
  - '[[2026-03-27-cli-ambiguous-states-prior-art-research]]'
---

# `cli-ambiguous-states` audit fix plan

## Steps

### Phase `P01` - Data safety

Fix defects that risk data loss: unsafe rmtree, destructive mcp.json rewrite, gitignore flag bug, uninstall ordering.

- [x] `P01.S01` - add rmtree_robust to safely unlink symlinks and clear NTFS read-only attributes, and replace production rmtree call sites; `src/vaultspec_core/core/helpers.py`.
- [x] `P01.S02` - surgically remove only the vaultspec-core key from .mcp.json on uninstall and merge into an existing file on install; `src/vaultspec_core/core/mcps_native.py`.
- [x] `P01.S03` - fix the gitignore_managed flag to reflect a pre-existing managed block, not only a freshly written one; `src/vaultspec_core/core/provision.py`.
- [x] `P01.S04` - reorder uninstall to delete the vaultspec framework directory last, collecting per-deletion errors; `src/vaultspec_core/core/uninstall.py`.

### Phase `P02` - Error visibility

Ensure sync and install errors reach the user instead of being silently swallowed.

- [x] `P02.S05` - display SyncResult.errors in sync output and set a non-zero exit code when errors are present; `src/vaultspec_core/cli/rendering_outcomes.py`.
- [x] `P02.S06` - propagate warnings through agent result merging; `src/vaultspec_core/core/agents.py`.
- [x] `P02.S07` - catch OSError in install, uninstall, and sync command handlers and convert filesystem errors to clean CLI messages; `src/vaultspec_core/cli/_errors.py`.
- [x] `P02.S08` - elevate preflight failure logging from debug to warning; `src/vaultspec_core/cli/root_preflight.py`.
- [x] `P02.S09` - add logging to silent catch clauses in config generation and sync; `src/vaultspec_core/core/config_gen.py`.

### Phase `P03` - Flag and logic fixes

Fix flag precedence, guard clauses, and per-pass error isolation in install and sync.

- [x] `P03.S10` - fix install --upgrade --dry-run flag precedence to show the upgrade-specific preview; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S11` - guard install --skip core when the vaultspec framework directory is absent; `src/vaultspec_core/core/provision.py`.
- [x] `P03.S12` - wrap each sync pass in its own try/except so one pass failure does not prevent the others; `src/vaultspec_core/core/sync.py`.
