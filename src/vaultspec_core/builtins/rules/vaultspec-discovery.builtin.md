---
name: vaultspec-discovery
---

# Discovery

Ground before changing: at each phase start, and before a session's first edit to source
or vault, at any horizon. The sequence is locate by meaning, read the epicenter whole,
confirm with grep.

1. **Locate by meaning.** Code:
   `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
   `--language` or `--path`). Decisions:
   `vaultspec-rag search "<intent>" --type vault --doc-type adr`. Orientation: the
   discovery verbs `vaultspec-core status [target]`, `vaultspec-core vault list`, and
   `vaultspec-core vault graph` (MCP: `status`, `find`). A small, well-named module is
   listed directly.
1. **Read** the epicenter file, or the nearest existing analogue when extending a
   feature, in full.
1. **Confirm** exact symbols and insertion points with a targeted grep.
1. For decisions, also list `.vault/adr/` filtered by feature; search alone misses
   lower-ranked or opaquely named records.

Do not lead with broad glob or grep sweeps on a large tree; grep is the confirmation
step. Where `vaultspec-rag` is not installed, the `vaultspec-core` discovery verbs and
grep carry the same sequence.
