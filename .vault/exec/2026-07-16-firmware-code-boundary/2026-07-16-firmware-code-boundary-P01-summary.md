---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# `firmware-code-boundary` `P01` summary

All three Steps (S01-S03) closed; the always-on boundary language is live.

- Modified: `src/vaultspec_core/builtins/system/01-core.md`
- Modified: `src/vaultspec_core/builtins/system/03-vaultspec.md`
- Modified: `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`
- Modified: matching `.vaultspec/` mirror files (CLI-regenerated)

## Description

Landed the canonical Code Stands Alone mandate in the core mandates list, the
removable-scaffolding characterization with one-way reference direction where the
framework introduces the `.vault/` record store, and the hierarchy clause placing
source code outside the documentation hierarchy. Each edit was made in the builtin
source only and rolled out through `vaultspec-core install --upgrade` and `sync`; prek
hooks passed on every commit. Verified by the boundary-phrasing grep and the passing
audit (status PASS).
