---
tags:
  - '#plan'
  - '#audit-fixes'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:d8c07ad2028e0dce8dbbdbafe2a5ef932bb1c266fdc5b1d508b5c30346d84cb3'
tier: L2
related:
  - '[[2026-02-22-audit-fixes-adr]]'
  - '[[2026-03-23-audit-fixes-research]]'
---

# Plan: Audit Remediations (Logging & Robustness)

## Steps

### Phase `P01` - RAG resilience

Wrap RAG document lookups so a missing GPU falls back to the filesystem path instead of raising

- [ ] `P01.S01` - wrap the rag document lookup in a GPUNotAvailableError handler that falls back to the filesystem path; `pyproject.toml`.

### Phase `P02` - CLI logging refactor

Initialize structured logging at CLI startup and replace informational print statements with logger calls

- [x] `P02.S02` - call configure_logging at cli startup; `src/vaultspec_core/cli/root_app.py`.
- [ ] `P02.S03` - replace informational print calls with logger calls while keeping structured stdout output; `src/vaultspec_core/cli`.

### Phase `P03` - Hydration visibility

Instrument template hydration with warning and debug logging for missing keys and successful replacements

- [x] `P03.S04` - add a logger and instrument the hydration replacement logic with warning and debug logging; `src/vaultspec_core/vaultcore/hydration.py`.

### Phase `P04` - Verification

Confirm the RAG fallback, CLI logging, and hydration logging behave correctly

- [ ] `P04.S05` - verify the rag fallback path when the gpu is unavailable; `pyproject.toml`.
- [ ] `P04.S06` - verify cli logging output stays clean on a routine command; `src/vaultspec_core/cli`.
- [ ] `P04.S07` - verify hydration logging during a vault create operation; `src/vaultspec_core/vaultcore/hydration.py`.
