---
generated: true
tags:
  - '#index'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
related:
  - '[[2026-06-27-rename-convergence-W01-P01-S01]]'
  - '[[2026-06-27-rename-convergence-W01-P01-S02]]'
  - '[[2026-06-27-rename-convergence-W01-P02-S03]]'
  - '[[2026-06-27-rename-convergence-W01-P02-S04]]'
  - '[[2026-06-27-rename-convergence-adr]]'
  - '[[2026-06-27-rename-convergence-plan]]'
  - '[[2026-06-27-rename-convergence-reference]]'
  - '[[2026-06-27-rename-convergence-research]]'
---

# `rename-convergence` feature index

Auto-generated index of all documents tagged with `#rename-convergence`.

## Documents

### adr

- `2026-06-27-rename-convergence-adr` - `rename-convergence` adr: `converge all rename CRUDs onto one transactional engine with domain locks and drift checks` | (**status:** `accepted`)

### exec

- `2026-06-27-rename-convergence-W01-P01-S01` - Create the shared rename-engine module with root-generalized \_assert_within and the symlink-safe restore helper
- `2026-06-27-rename-convergence-W01-P01-S02` - Implement RenameTransaction: caller-supplied snapshot, containment-checked case-safe rename, record-write/create/dir, context-manager rollback, and domain-lock acquisition
- `2026-06-27-rename-convergence-W01-P02-S03` - Drive rename_feature through RenameTransaction, passing its non-archive snapshot set, with no behavior change
- `2026-06-27-rename-convergence-W01-P02-S04` - Run the rename_feature and structure case-rename suites to confirm byte-identical behavior

### plan

- `2026-06-27-rename-convergence-plan` - `rename-convergence` plan

### reference

- `2026-06-27-rename-convergence-reference` - `rename-convergence` reference: `rename surfaces, shared primitives, lock, and integrity-check landscape`

### research

- `2026-06-27-rename-convergence-research` - `rename-convergence` research: `converging CLI rename CRUDs onto one engine with lock and drift check`
