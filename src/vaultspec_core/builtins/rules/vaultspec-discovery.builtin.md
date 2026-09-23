---
name: vaultspec-discovery
---

# Discovery

Discover before changing: at each phase start, and before a session's first edit to
source or vault, at any horizon. Run the steps in order: locate by meaning, read the
epicenter whole, confirm with grep, list the decisions.

1. **Locate by meaning.**
   - Code: `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
     `--language` or `--path`).
   - Search decisions and vault facts with `vaultspec-core vault search "<question>"`
     (MCP: `search`); when it declines or fails, run the next step its reply names.
   - Orientation: `vaultspec-core status [target]` and
     `vaultspec-core vault list [type]` (MCP: `status`, `find`), and
     `vaultspec-core vault graph` (CLI only).
   - A small, well-named module is listed directly.
1. **Read** the epicenter file, or the nearest existing analogue when extending a
   feature, in full.
1. **Confirm** exact symbols and insertion points with a targeted grep.
1. **List decisions.** Run `vaultspec-core vault list adr` (MCP: `find`) across all
   features. Add `--feature` only to cut noise. Search can miss a record, so this step
   always runs. Under an approved plan, the plan's linked decisions satisfy this step,
   unless the Step reaches beyond their scope. Read each accepted decision that covers
   the scope in full, and follow its evidence links. This discovery does not itself
   require a persisted Research or Reference record.

## Reading a search reply

MCP and `--json` replies carry the verdict as a value; the CLI prints it as a sentence.

- An excerpt is triage. Read the record whole before you rely on it.
- A premise conflict means the record contradicts something the question assumed.
  Re-check that assumption before you act on it.
- "nothing in the vault answers this" (`nothing_answers`) is evidence that no record
  covers the question. Still list the decisions.
- "no record that was read answers this" (`none_read_answers`) means some records were
  not read. It is not evidence of absence. List the decisions and grep `.vault/`.
- A reply that declines or fails names a next step. Run it. When that step is
  `vaultspec-core vault list` plus grep, it is also step 4: run it once.

## Without semantic search

Do not lead with broad glob or grep sweeps on a large tree; grep is the confirmation
step. Where `vaultspec-rag` is unavailable, locate code with a targeted grep, and say in
your report that discovery ran without semantic search. When a search reply names a
`vaultspec-rag` search that cannot run (not installed, down, or not indexed), run
`vaultspec-core vault list` (MCP: `find`) and grep `.vault/` instead, and say the same.
