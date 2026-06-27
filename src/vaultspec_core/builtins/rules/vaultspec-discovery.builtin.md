---
name: vaultspec-discovery
---

# Codebase and intent discovery

Begin every pipeline phase - Research, ADR, Plan, Execute - by grounding in what the
project already decided and built. The project's own benchmarking is unambiguous: a
semantic-search-led hybrid sweep finds a feature fastest and at the lowest context cost
\- roughly 1.3-2x cheaper than broad keyword search on a large tree - and recalls
governing decisions with near-zero noise. Lead with it. The validated sequence is locate
by meaning, read the epicenter whole, confirm with grep:

1. **Locate by meaning.** For code, lead with
   `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
   `--language`/`--path`); it reaches the right file in about one call where broad
   globbing floods context. For decisions and intent,
   `vaultspec-rag search "<intent>" --type vault --doc-type adr` - the directed ADR
   filter, sharper than catch-all `--type vault`. `vaultspec-core status [target]`,
   `vaultspec-core vault list`, and `vaultspec-core vault graph` are first-class for
   orientation, in-flight plan state, and project health - reach for them to get your
   bearings on intent. For a small, well-named module, list the directory.
1. **Read** the epicenter file - or, when extending a feature, the nearest existing
   analogue - in full. This whole-file read is the breakthrough in nearly every run.
1. **Confirm** exact symbols and insertion points with a targeted grep, which is sharper
   than semantic search at exact-symbol lookup.
1. For decision discovery, round out recall by listing `.vault/adr/` and filtering by
   feature - semantic search alone can miss lower-ranked or opaquely-named records.

Do not lead with broad `Glob`/grep sweeps; their context cost scales badly on large
codebases, and grep earns its place at the confirmation step. Where `vaultspec-rag` is
not installed, the `vaultspec-core` discovery verbs and grep carry the same sequence.
