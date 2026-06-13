---
tags:
  - '#plan'
  - '#vault-graph-ref'
date: '2026-06-13'
modified: '2026-06-13'
tier: L1
related:
  - '[[2026-06-13-vault-graph-ref-adr]]'
  - '[[2026-06-13-vault-graph-ref-research]]'
---

# `vault-graph-ref` plan

- [ ] `S01` - add a git blob corpus reader enumerating and reading vault blobs at a ref via subprocess git; `src/vaultspec_core/graph/refscan.py`.
- [ ] `S02` - add a VaultGraph ref-construction path with cache disabled, migrations skipped, doc-type from the tree path; `src/vaultspec_core/graph/api.py`.
- [ ] `S03` - add --ref to the graph verb with typed errors and add the ref envelope key; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `S04` - cover the ref path with real-git tests and update the bundled reference and docs; `src/vaultspec_core/tests/cli/test_graph_ref.py`.

## Description

Deliver `vault graph --json --ref <ref>` per the accepted ADR: read the vault corpus
from git blobs at a ref through subprocess git, build the graph with the cache disabled
and the working-tree migration pass skipped, and emit the unchanged
`vaultspec.vault.graph.v2` envelope with an added `ref` key and virtual node paths. A
non-repository workspace or an unresolvable ref fails with a typed error rather than a
working-tree fallback.

## Parallelization

`S01` (blob reader) and `S02` (graph build path) are sequential: the build consumes the
reader's output. `S03` (CLI surface and envelope) depends on `S02`. `S04` (tests and
docs) lands last and exercises the whole path against a real throwaway git repository.

## Verification

`vault graph --json --ref <sha>` against a repository whose vault changed between commits
returns the corpus as it stood at that ref, identical in shape to a working-tree build of
the same corpus; the working-tree graph cache is neither read nor written by the ref
path; a missing ref and a non-git workspace each exit non-zero with a typed message;
`ruff`, `ty`, and the new tests are green.
