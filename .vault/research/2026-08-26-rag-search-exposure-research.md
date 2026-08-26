---
tags:
  - '#research'
  - '#rag-search-exposure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:18e54276806d8b7bbd993a0efbd321a147d6b3cb4df860b3eb630cacd0a440a2'
related:
  - "[[2026-08-26-rag-search-exposure-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace rag-search-exposure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `rag-search-exposure` research: `How vaultspec-core exposes vaultspec-rag search today`

<!-- Lead: the question, why it matters to `rag-search-exposure`, and what was
     concluded - the evidence picture, not a decision. -->

## Findings

The question: what does core actually expose of rag's semantic search, how
far is it from what rag offers, and what would exposing more cost. It matters
because the two products have both moved substantially since the coupling was
last examined, and nothing in core observes rag at all.

**Core exposes no semantic search, and never has.** No search tool in
`src/vaultspec_core/mcp_server/tools/`, no search command in
`src/vaultspec_core/cli/`, no HTTP client, no `vaultspec_rag` import. The
`find` tool (`src/vaultspec_core/mcp_server/tools/documents.py:942`) takes
`feature` / `type` / `date` / `body` / `limit` and no query string: it is a
filtered directory listing.

**The coupling that exists is prose.** Eight builtin agent documents under
`src/vaultspec_core/builtins/agents/` instruct agents to shell out to
`vaultspec-rag search "<concept>" --type code` and
`--type vault --doc-type adr`; six carry a hand-written fallback clause for
rag's absence. It is unversioned, untestable, invisible to the MCP host, and
cannot express rag's grammar.

**rag's surface is far larger.** `vaultspec-rag@0.4.4` exposes `search_vault`,
`search_codebase`, `search_documents`, and `search_combined` (22 parameters),
plus `get_code_file`, four reindex verbs, `get_index_status`, and two clean
verbs (`src/vaultspec_rag/mcp/_tools.py`). The filter-token grammar in
`src/vaultspec_rag/search/_parsing.py:26-47` covers `type: feature: date: tag:
lang: path: func: class: nodetype: intent: status: exclude: only: include:`,
the last three multi-value. Beyond tokens: `intent` ranking profiles,
`like_ids` / `unlike_ids` relevance feedback, `prefer`, `dedup_locales`, and
extractor filters.

**The capability asymmetry is inside rag, not core.** rag's own CLI
(`src/vaultspec_rag/cli/_search.py:1059-1248`) has no `--intent`, no
`--like` / `--unlike`, and no domain-filter flags; those are MCP-only or
inline-token-only. Core's prose drives the CLI, so core's advertised path is
structurally a tier behind rag and cannot close the gap by trying harder.

**Version knowledge is absent.** Core's only rag constraint was
`vaultspec-rag[mcp]>=0.3.8` in the PEP 735 `dev` group (`pyproject.toml:110`) -
never published, never a runtime constraint, and a full minor release stale
against rag 0.4.4. Nothing consumed it, so nothing could notice. Core has no
runtime view of rag's version, and `doctor` had no rag probe.

**The dependency direction forecloses pinning.** rag depends on core: it
vendors core in its venv, ships `vaultspec-core.builtin.json`, and imports
core's `write_package_declaration` directly
(`src/vaultspec_rag/commands/_mode.py:232`). Core already maintains a
back-compat constant for rag consumers floored on core 0.1.38
(`src/vaultspec_core/core/workspace_mode.py:168`). Core cannot pin rag without
inverting that direction and creating a release cycle.

**The per-package floor map is owned by the package it names.** The schema 2.0
`packages` map carries `minimum_version` per distribution with a skew handshake
(`src/vaultspec_core/core/workspace_mode.py:979-1010`). rag writes its own
entry and reads its own floor back out of it
(`src/vaultspec_rag/commands/_mode.py:231-235`), and that floor feeds rag's
gate. A floor written there by core would therefore be actuation - capable of
making rag refuse its own invocation - not advice. The write is lock-guarded
and sibling-preserving, so the hazard is authorship and semantics, not
corruption, which is what makes it easy to mistake for safe mechanism reuse.

**rag fails closed on version skew, deliberately.** Every data-plane call
resolves a discovery pointer and refuses a foreign release
(`src/vaultspec_rag/mcp/_tools.py:199-223`), because an unrecognised request
field would otherwise be dropped silently and the answer computed against a
different candidate set behind a 200. A core-side proxy would sit in front of a
client that fails closed and would surface a fatal error core cannot resolve.

**rag exempts its observability verbs from that gate.** `stop`, `status`,
`doctor`, `logs`, and `jobs` work against a daemon of any release
(`src/vaultspec_rag/serviceclient/_compat.py:217-221`) precisely because they
are how an operator observes and resolves a mismatch. `vaultspec-rag server
doctor` is therefore the one surface designed to answer under the degraded
conditions where a core-side liveness probe would be least trustworthy.

**The loopback transport is better defended than it looks, but its trust root
is a file.** `src/vaultspec_rag/_loopback_http.py` pins 127.0.0.1, disables
proxy inheritance, and refuses redirects. However `resolve_data_plane_service`
takes the port *and* the version that validates it from the same on-disk
discovery payload (`src/vaultspec_rag/serviceclient/_compat.py:226-232`), so
the release check defeats an outdated peer, not a forged one: a tampered or
stale pointer supplies both the redirect and the version that blesses it. The
concern is discovery-file integrity, not port squatting.

**Other risks a proxy would inherit.** Every rag search tool accepts
`project_root`, which would let a caller redirect a root-bound core tool
outside its workspace; `get_code_file(path)` is an unbounded arbitrary-file
read where core's own body path is tiered and byte-accounted; and search
results are third-party text (vendored deps, generated code, locale files)
where core's tools today return only user-authored vault documents. rag's
noise-domain profile demotes those sources for relevance, not as a trust
boundary.

**One shape core already owns.** The `vaultspec-rag` entry in `.mcp.json` is
rendered by core's own `render_launch_for_mode`
(`src/vaultspec_core/core/mcps_mode.py:60-98`), which is parameterized by
distribution and module so a companion substitutes through it. Reading that
entry is core reading its own output - the one observation available at zero
coupling cost.

The evidence favors reporting rag's provisioning rather than proxying its
search. What the ADR must settle: whether core probes liveness at all, how the
floor is declared given that the packages map is the wrong home for it, and
what the degraded discovery path should be once prose stops carrying it.

## Sources

<!-- Each locator cited above, once: `path:line` backtick locators for code,
     bare URLs for external references. Flag unverified general-knowledge
     claims. -->
