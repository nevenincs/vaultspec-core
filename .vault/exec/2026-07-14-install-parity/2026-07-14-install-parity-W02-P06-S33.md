---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S33'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Leave the --local-only flag and its per-host local-only.json marker unchanged as an orthogonal storage-backend choice, and add a regression test asserting it is not folded into the shared mode declaration

## Scope

- `src/vaultspec_rag/config.py`

## Description

- Leave `src/vaultspec_rag/config.py` `persist_local_only` and the per-host
  `local-only.json` marker unchanged, confirming the backend selection stays an
  orthogonal storage choice, not a placement mode.
- Add a regression test asserting an install never folds a backend field into
  the shared per-package mode declaration, and that the local-only marker lives
  in the per-host status directory, disjoint from `.vaultspec/workspace.json`.

## Outcome

The `--local-only` backend marker and the provisioning-mode declaration remain
independent axes. After a mode install the workspace declaration entry carries
only `install_mode` (and optionally `minimum_version`), never a backend key,
and `persist_local_only` writes to the isolated status directory verified via
the `VAULTSPEC_RAG_STATUS_DIR` override.

## Notes

No production code changed for this step; the requirement was to preserve the
existing orthogonality and lock it under a regression test. The test lives with
the other mode tests in `src/vaultspec_rag/tests/test_install_mode.py`.
