---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S07'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add legacy v1-to-v2 fold tests and mixed-package configuration round-trip tests using WorkspaceFactory and real filesystem writes

## Scope

- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add `TestLegacyV1Fold`: a hand-written schema 1.0 single-key file folds to the core entry (facade and per-package views agree, floor read as `minimum_version`), the floor-absent case folds cleanly, and the next per-package write migrates the whole file to schema 2.0 shape with no leftover top-level single-key fields.
- Add `TestSchemaV2RoundTrip`: DEV round-trips through both the per-package helper and the facade, a per-package floor round-trips, an unset floor is omitted from the entry, and an absent package entry reads as `None`.
- Add `TestMixedPackageConfig`: a core-dependency/rag-tool configuration reads each entry independently, single-package and facade writes preserve the sibling entry, the facade returns `None` when only a sibling is declared, and a PEP 503 underscore spelling writes the canonical hyphenated key.
- Add `TestV2CorruptEntries`: an out-of-vocabulary mode, a non-object entry, and a non-object `packages` map each raise the typed error with its distinct message.
- Update the imports to pull in `PackageDeclaration`, `read_package_declaration`, and `write_package_declaration`.

## Outcome

The schema 2.0 surface, the legacy read-fold, the mixed-package model, and the strict-corrupt contract are covered by real-filesystem tests through the WorkspaceFactory `factory` fixture, with zero mocks, patches, stubs, or skips. The full workspace-mode module now has 35 unit tests passing (16 added). Ruff and scoped ty clean.

## Notes

No incidents. Tests assert against the real committed bytes (`json.loads` of the written file) for wire-shape claims and through the public read helpers for semantics, so a regression in either the fold or the sibling-preservation write path fails a concrete assertion rather than passing silently.
