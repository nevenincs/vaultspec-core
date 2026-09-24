---
name: vaultspec-discovery
---

# Discovery

Discover before changing: at each phase start, and before a session's first edit to
source or vault, at any horizon. Run the steps in order.

1. **Locate by meaning.**
   - Code: `vaultspec-rag search "<concept and domain nouns>" --type code`.
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
   features; add `--feature` only to cut noise. Search can miss a record, so this step
   runs before a plan or ADR is written and for work outside a plan. Read each covering
   accepted decision in full, and follow its evidence links.

Under an approved plan, its linked decisions replace the decision search and step 4 for
Steps inside their scope. Code search still runs.

## Reading a search reply

MCP and `--json` replies carry the verdict as a value; the CLI prints it as a sentence.

- An excerpt is triage. Read the record whole before you rely on it.
- A premise conflict means the record contradicts something the question assumed.
  Re-check that assumption before any listing or grep.
- "nothing in the vault answers this" (`nothing_answers`) is evidence that no record
  covers the question. Step 4 still runs.
- "no record that was read answers this" (`none_read_answers`) is not evidence of
  absence. Run step 4 and grep `.vault/` for the types asked about.
- A reply that declines or fails names a next step. Run it. A listing of all types or
  `adr`, with no `--feature` or `--date`, is also step 4; any other is not.

## Without semantic search

Do not lead with broad glob or grep sweeps on a large tree; grep is the confirmation
step. Where `vaultspec-rag` is unavailable, locate code with a targeted grep, and say in
your report that discovery ran without semantic search. When
`vaultspec-core vault search` cannot run (CLI missing, MCP down), or its reply names a
`vaultspec-rag` search that cannot run (not installed, down, or not indexed), run
`vaultspec-core vault list` (MCP: `find`) and grep `.vault/` instead, and say the same.
That listing is also step 4.
