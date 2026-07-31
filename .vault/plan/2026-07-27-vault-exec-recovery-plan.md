---
tags:
  - '#plan'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:a79684d34a34deb5253f72cfbc6e53ca21d1518397abecff9e3ccf1394195b3b'
tier: L2
related:
  - '[[2026-07-27-vault-exec-recovery-adr]]'
  - '[[2026-07-27-vault-exec-recovery-research]]'
---

# `vault-exec-recovery` plan

## Description

Implement the accepted recovery decision: explicit `vault exec` commands repair only proven historical execution mappings. The work adds typed operations, a narrow CLI surface, real-file verification, and an operator-run recovery of the RAG vault.

## Steps

### Phase `P01` - Recovery command surface

Deliver explicit, validated execution-record recovery operations and prove their behavior against real vault files.

- [x] `P01.S01` - Implement typed execution-record recovery operations with atomic writes and archive handling; `src/vaultspec_core/vaultcore`.
- [x] `P01.S02` - Expose relink, retire, and detach commands with JSON and dry-run contracts; `src/vaultspec_core/cli`.
- [x] `P01.S03` - Prove recovery preconditions, body preservation, and command contracts against real vault files; `tests`.
- [x] `P01.S04` - Apply verified recovery operations to the RAG vault and verify its mapping check; `Y:/code/vaultspec-rag-worktrees/main/.vault`.

## Parallelization

P01.S01, P01.S02, and P01.S03 have a hard dependency chain because the CLI depends on typed recovery operations and its integration tests depend on the CLI. P01.S04 follows code review and runs only on the verified historical record set.

## Verification

Run the focused core and CLI tests, lint the changed modules, verify generated CLI references, complete independent code review, and run `vault check exec-mapping` against the target RAG vault after the explicit recovery commands apply.
