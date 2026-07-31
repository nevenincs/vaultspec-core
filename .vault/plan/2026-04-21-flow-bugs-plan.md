---
tags:
  - '#plan'
  - '#flow-bugs'
date: '2026-04-21'
modified: '2026-07-31'
body_hash: 'sha256:62066f7cc8746a6f3d136a1cefd3f4d2c7806d67d7f0b9f089764ba055a4aeaf'
tier: L2
related:
  - '[[2026-04-21-flow-bugs-adr]]'
  - '[[2026-04-21-flow-bugs-research]]'
---

# `flow-bugs` plan: install-layer hygiene fixes

### Phase `P01` - install-layer hygiene

Fix five install-layer hygiene bugs so managed surfaces stay reconciled with git and vault state.

- [x] `P01.S01` - make check-providers respect deletions via diff-filter=ACMR; `src/vaultspec_core/core/git_artifacts.py`.
- [x] `P01.S02` - lock advisory-lock sentinels for companion files in the managed gitignore block; `src/vaultspec_core/core/gitignore.py`.
- [x] `P01.S03` - skip pre-commit-config scaffolding when prek.toml is present; `src/vaultspec_core/core/prek_boundary.py`.
- [x] `P01.S04` - untrack historically-tracked managed paths on install; `src/vaultspec_core/core/provision.py`.
- [x] `P01.S05` - rewrite incoming wiki-link references on document rename; `src/vaultspec_core/vaultcore/checks/structure.py`.

### Phase `P02` - lingering issue audit

Sweep for similar unreconciled managed-surface patterns after the hygiene fixes land.

- [ ] `P02.S06` - audit managed-surface reconciliation patterns and advisory-lock leak paths across the install layer; `src/vaultspec_core/core`.
