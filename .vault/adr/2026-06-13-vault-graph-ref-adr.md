---
tags:
  - '#adr'
  - '#vault-graph-ref'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-vault-graph-ref-research]]'
---

# `vault-graph-ref` adr: `ref-scoped vault graph` | (**status:** `accepted`)

## Problem Statement

`vault graph --json` reads the vault corpus of whatever working tree it runs in. Any
tool that maps a repository's full branch and worktree landscape and ingests the
declared-edge graph once per corpus view - one vault as it stands on one line of
development - can today obtain that graph for a ref only by checking the ref out and
running core inside it, which costs a worktree per view and leaves remote branches with
no checkout unreadable. Issue #160 asks core to make its declared-edge graph
ref-addressable: `vault graph --json --ref <branch|sha>` resolving documents from blobs
at the ref, read-only, with no working-tree mutation, under the existing
`vaultspec.vault.graph.v2` envelope.

## Considerations

The grounding research (`2026-06-13-vault-graph-ref-research`) establishes that the read
seam is unusually clean. `VaultGraph._rebuild_from_files` touches the filesystem in
exactly one place - a single `read_text` per document - and every parser downstream
(`parse_vault_metadata`, `parse_frontmatter`, `extract_wiki_links`,
`extract_related_links`) is already content-bound, accepting strings rather than paths.
The only path-coupled classifier, `get_doc_type`, derives a document's type from its
location under the docs directory, which a tree-path string reproduces exactly. The
envelope is assembled by `to_dict` from a networkx serialization plus injected `root`,
`feature`, `derived_edges`, and `metrics`. The decision is therefore less about feasibility
than about which blob-reading mechanism to adopt and how to keep the historical read from
contaminating the working-tree cache.

## Constraints

The project ships no git library and deliberately minimizes dependencies. Reading blobs
must therefore use the subprocess `git` pattern already present in the codebase and test
suite (`git ls-tree -r --name-only <ref> -- <docs_dir>` to enumerate, `git cat-file blob`
or `git show <ref>:<path>` to read), not a new `gitpython` or `pygit2` dependency. The
feature is git-only by nature: it must fail cleanly with a typed error when the workspace
is not a git repository or when the ref does not resolve, never fall back to a working-tree
read that would silently answer for the wrong corpus. The graph cache fingerprints files
by size and mtime, which do not exist for blobs; a ref-scoped build must run with caching
disabled so it neither consumes nor writes the working-tree cache. The migration runner
that `scan_vault` triggers on the working tree has no meaning for a read-only historical
snapshot and must be skipped on the ref path. No parent feature is unstable: the parser
and envelope are mature and already exercised by the working-tree path.

## Implementation

A ref-scoped corpus provider sits beside the filesystem scanner. Given a ref and the
configured docs directory, it enumerates the vault blobs at that ref through git and reads
each blob's bytes, yielding `(virtual_tree_path, content)` pairs that mirror what
`scan_vault` plus `read_text` yield today. `VaultGraph` gains a construction path that
consumes those pairs instead of walking the working tree, with caching off and the
migration pass skipped; document-type classification reads the tree-path string rather than
calling `relative_to`. The verb gains a `--ref <ref>` option that selects this path,
resolves the ref up front, and errors typed-and-clean on a non-repository workspace or an
unresolvable ref. The JSON envelope stays `vaultspec.vault.graph.v2` with two additions
that do not alter any node or edge shape: a top-level `ref` key naming the snapshot beside
the existing `root`, and each node's `path` carrying the virtual tree path. Concrete
function signatures and the blob-enumeration command details belong in a `{reference}`
document produced at implementation time, not here.

## Rationale

The subprocess approach keeps the dependency footprint flat and matches the only git
access pattern the project already trusts. Reusing the content-bound parser and the v2
envelope means the historical graph is structurally identical to the working-tree graph,
so any consumer ingests both through one code path and one schema - the whole point of
the request. Disabling the cache and skipping migrations on the ref path is not an
optimization choice but a correctness boundary: a read-only view of history must not write
working-tree state nor be served stale working-tree data. Adding `ref` rather than
reusing `root` keeps a historical snapshot self-describing without overloading a field
whose working-tree meaning consumers already depend on.

## Consequences

Any tool that speaks the v2 envelope gains the declared graph for every ref without
provisioning a worktree per view, reading history for free. The cost is that core takes
on its first production dependency on the `git` executable being present and on the
assumption that blob bytes decode as UTF-8 text; both need explicit, typed failure modes
rather than tracebacks. Performance is bounded by one `git cat-file` per document,
acceptable for a per-view cadence but not for tight loops, and the absence of a ref-keyed
cache means repeated reads of the same ref recompute. The path
opens a natural follow-on - an `as_of` historical reconstruction that walks multiple refs -
but that is explicitly out of scope here.

## Codification candidates

- **Rule slug:** `ref-scoped-reads-bypass-worktree-cache`.
  **Rule:** Any vault read scoped to a git ref must run with the graph cache disabled and
  the working-tree migration pass skipped, and must never fall back to a working-tree read
  when the ref or repository does not resolve.
