---
tags:
  - '#research'
  - '#vault-graph-ref'
date: '2026-06-13'
modified: '2026-06-13'
related: []
---

# `vault-graph-ref` research: `ref-scoped vault graph from the git object database`

GitHub issue #160 asks core to let `vault graph --json` read a vault corpus at an
arbitrary git ref (`--ref <branch|sha>`) directly from the object database, without a
working-tree checkout, emitting the same versioned envelope. A tool that maps a
repository's whole branch and worktree landscape and ingests the declared-edge graph
once per corpus view can today obtain that graph only for refs that have a checkout, so
remote branches with no checkout are unreadable. This research grounds the seam, the
parser's path-coupling, the git tooling gap, and the wire-format delta against the live
code.

## Findings

### The command and its current working-tree binding

The verb lives in `src/vaultspec_core/cli/vault_cmd.py` as `cmd_graph`. It calls
`apply_target(target)`, constructs `VaultGraph(_get_ctx().target_dir)`, and for `--json`
calls `graph.to_dict(...)` wrapped by `json_envelope("vault.graph", ..., version=2)`,
which yields the schema string `vaultspec.vault.graph.v2`. Every path runs against the
working tree; there is no `--ref` today.

### The single filesystem seam

The corpus read is narrow. `scan_vault(root_dir)` in
`src/vaultspec_core/vaultcore/scanner.py` does a plain `docs_dir.rglob("*.md")` over the
working tree and yields `Path` objects, skipping `.obsidian` and `_archive`.
`VaultGraph._rebuild_from_files` in `src/vaultspec_core/graph/api.py` is the hot path,
and its only filesystem touch is a single `content = path.read_text(encoding="utf-8")`.
Everything downstream consumes the raw string.

### The parser is already content-bound

`parse_vault_metadata(content)` and `parse_frontmatter(content)` in
`src/vaultspec_core/vaultcore/parser.py` both take a `str` and return parsed structures;
`extract_wiki_links` and `extract_related_links` in
`src/vaultspec_core/vaultcore/links.py` are pure string and list functions. None is
path-bound, so substituting blob bytes for `path.read_text()` requires zero parser
refactor. The one exception is `get_doc_type(path, root_dir)` in `scanner.py`, which
classifies a document from its location via `path.relative_to(docs_dir)` and
`parts[0]`. A blob walk already knows each blob's tree path (for example
`.vault/adr/foo.md`), so the same classification reproduces from the tree-path string;
this is a small isolated change, not a structural one.

### No git tooling exists; the project pattern is subprocess

`pyproject.toml` declares no git library (no `gitpython`, `pygit2`, or `dulwich`).
Production code never reads the object database; the only git subprocess calls are
install-time `git ls-files` / `git rm --cached` in
`src/vaultspec_core/core/commands.py`, and git-repo discovery in
`src/vaultspec_core/config/workspace.py` walks for `.git` without reading history. The
established way to read blobs without a new dependency is
`git ls-tree -r --name-only <ref> -- <docs_dir>` to enumerate, then
`git cat-file blob <sha>` (or `git show <ref>:<path>`) to read - the same subprocess
pattern the test suite already uses. This keeps the project's minimal-dependency stance
(pure-Python PageRank, no numpy) intact.

### The cache must be bypassed, never shared

The graph cache in `src/vaultspec_core/graph/cache.py` lives at
`<docs_dir>/data/.graph-cache/graph.json` and fingerprints each file as
`(st_size, st_mtime_ns, sha256)`. Those are working-tree inode facts with no slot for a
ref. A ref-scoped build has no mtimes and must construct with `use_cache=False` so it
neither reads nor writes the working-tree cache; otherwise a historical build would
poison the next working-tree build.

### The wire-format delta is two keys

`VaultGraph.to_dict(...)` builds `data` from networkx `node_link_data` plus injected
`derived_edges`, `root`, `feature`, and `metrics`; each node carries `path` among its
attributes. To stay schema-compatible while expressing ref semantics, the envelope needs
a companion `ref` key beside `root`, and each node's `path` becomes the virtual tree
path (or `null`). No node or edge attribute changes shape, so
`vaultspec.vault.graph.v2` remains the contract.
