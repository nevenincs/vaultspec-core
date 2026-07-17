---
name: vaultspec-rag-discovery
description: Semantic codebase and architecture-decision discovery with vaultspec-rag - find code and the ADRs that govern it by meaning, then narrow with advanced filters and noise controls. Use to locate where or how something is done, or the decision behind it, instead of guessing identifiers or sweeping with keyword/grep search.
---

# Semantic discovery with vaultspec-rag

vaultspec-rag finds things by MEANING. When you need to locate where or how something is done
and do not already know the exact symbol, lead with a semantic search rather than a keyword
sweep: keyword search only finds the words you already guessed, while semantic search finds the
concept even when the code names it differently. The project's own discovery benchmarking is
the basis for leading with it - a semantic-led hybrid sweep reaches the right file in about one
call at roughly 1.3-2x less context than a broad grep or glob on a large tree, and recalls the
governing decision with almost no noise.

Treat vaultspec-rag as a discovery instrument and grep as the exact-symbol confirmer: a search
lands you on the right surface, grep pins the precise line. Never conclude "there is no such
site" from a search alone - confirm with grep.

## The method: locate by meaning, read, confirm

1. **Locate by meaning.** Run a semantic search to reach the epicenter file (code) or the
   governing record (a decision). One tight query gets you there.
1. **Read the epicenter whole.** Open the top file (or the nearest existing analogue) in full.
   This whole-file read is the step that actually grounds you.
1. **Confirm with grep.** Pin the exact symbol, call site, or insertion point with a targeted
   grep, which is sharper than semantic search at exact-name lookup.

## Two corpora: code and decisions

vaultspec-rag searches two things. Choose with `--type`:

- **Code** (`--type code`) - the source tree, chunked by structure.
- **The vault** (`--type vault`) - the project's decision and planning records. Architecture
  decisions live as ADRs, reached with `--doc-type adr`.

Bind them together: find the code that does something, then find the ADR that decided why it
does it that way.

## Write queries that both halves can match

The index is hybrid: dense embeddings match meaning, sparse vectors match exact terms, and a
cross-encoder reranks the top hits. A good query feeds both halves - describe the behaviour in
a short phrase (that drives the semantic half) AND name the concrete domain nouns the target
would use (that drives the exact-match half). A bare keyword or pure prose finds less than both
together. One concept per query; narrow with filters rather than piling clauses into the text.

Phrase the target as a thing, not as a question - a noun phrase for the concept lands better
than a "what happens when X" flow question. Search for `"file lock around the incremental index write"`, not `"what happens when two indexers run at once"`.

## Discover code

`--type code` searches source by meaning.

```
uvx vaultspec-rag search "retry backoff around failed webhook delivery" --type code
uvx vaultspec-rag search "file lock acquired around the incremental index write" --type code
```

Narrow code results with these flags:

- `--language <lang>` - one programming language.
- `--path <exact/relative/path>` - one exact project-relative path.
- `--include-path <glob>` / `--exclude-path <glob>` - keep or drop files by glob (repeatable).
- `--structure <kind>` - one source-code structure, e.g. a function or class definition.
- `--function-name <name>` / `--class-name <name>` - results inside a named function or class.

```
uvx vaultspec-rag search "encode batch on the gpu" --type code --language python
uvx vaultspec-rag search "request handler" --type code --include-path "src/**" --exclude-path "**/legacy/**"
```

## Discover architecture decisions

When you need the WHY - the rationale, constraints, or the decision behind code - search the
vault's ADRs, not the source.

```
uvx vaultspec-rag search "decision on gpu lock scope around the forward pass" --type vault --doc-type adr
```

`--doc-type` accepts `adr`, `audit`, `plan`, `reference`, `research`, and `exec`
(comma-separate to union several). Narrow the vault further with `--feature <tag>`,
`--date <yyyy-mm-dd>`, and `--tag <tag>` (no leading `#`).

```
uvx vaultspec-rag search "retry policy tradeoffs" --type vault --doc-type adr,research --feature webhooks
```

## Cut noise with domain filters

Semantic search competes production code against its own noise - overlapping tests, parallel
locale files, generated and vendored trees, worktree clones. Every code chunk carries a domain
derived from its path: `prod`, `tests`, `docs`, `locale`, `generated`, `vendored`, `worktree`.
Code search is production-biased by default: it hides duplicate/derivative domains (`generated`,
`worktree`) and demotes `tests`, `docs`, `locale`, and `vendored` beneath production, and it
collapses locale-variant duplicates to a single result. So a plain query already leads with
production.

When noise still crowds a page, narrow by DOMAIN rather than raising `--max-results` and reading
past it. Steer with inline query tokens - they ride in the query string (no flags), take
comma-separated sets, and repeat:

```
uvx vaultspec-rag search "fixture setup helpers exclude:tests" --type code
uvx vaultspec-rag search "auth token validation only:prod" --type code
uvx vaultspec-rag search "translation table lookup include:locale" --type code
uvx vaultspec-rag search "payment capture path exclude:tests,docs,vendored" --type code
```

- `exclude:<domains>` hides those domains for this search.
- `only:<domains>` restricts results to those domains - e.g. `only:tests` to find just the
  tests that exercise a behaviour.
- `include:<domains>` re-admits a domain the default profile hides or demotes - e.g.
  `include:locale` when you actually want the translation tables.

Two more controls compose with domains:

- `--prefer production|tests|documentation` biases the ranking toward one kind of file without
  removing the others.
- `--dedup-locales` / `--no-dedup-locales` forces locale-duplicate collapse on or off (on by
  default).

```
uvx vaultspec-rag search "greeting string" --type code --no-dedup-locales   # audit every locale
uvx vaultspec-rag search "encode batch" --type code --prefer production
```

## Read results as clusters, not just the top hit

Read the directory CLUSTERING across the top few hits, not only the single top score. When
scores are close or collapse, the repeating module or feature folder is usually the right
surface even if no one line is a perfect match. Skip near-identical hits that are one signal
(parallel locale files return the same string several times), and be wary of a test docstring
that outranks the production module - the domain filters above exist to clear exactly that.

## Operating notes

Server mode is the default backend; the running service auto-reindexes on file changes, so DO
NOT manually reindex during normal work. If a search reports the service is down, start it with
`uvx vaultspec-rag server start` (small or offline projects opt into the on-disk local backend
with `--local-only`). The full option set is `uvx vaultspec-rag search --help`. The same search
is available through MCP as the `search_codebase` and `search_vault` tools.
