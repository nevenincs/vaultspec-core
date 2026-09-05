---
name: vaultspec
---

# Vault records

Every `.vault/` record belongs to one feature and is scaffolded by its owning verb: the
`create` tool where the MCP server is connected, otherwise
`vaultspec-core vault add <type> --feature <feature>`. The verb owns the filename and
the frontmatter; the author writes body prose only. The frontmatter schema, tag pair,
placeholders, and filename patterns are catalogued in
`.vaultspec/reference/vault-schema.md`; never hand-write them.
`vaultspec-core vault check all --fix` repairs drift and strips leftover template hints.

## Record types

- **Research** (`.vault/research/`) grounds a decision: claim-first findings, each with
  a re-fetchable locator, and a `## Sources` list. It frames options; it never records
  the decision. Requires nothing.
- **Reference** (`.vault/reference/`) grounds work in code: how this or another codebase
  implements the thing, as patterns with `file:line` locators, not copied code. Requires
  nothing.
- **ADR** (`.vault/adr/`) records one decision and only the decision, citing research
  and reference by stem, never restating their evidence. Requires at least one Research
  or Reference record. Its status token lives in the heading and is author-edited body
  prose: `proposed` at scaffold, `accepted` on the approval reply. A refinement amends
  the accepted record in place, with the same approval reply; a reversal scaffolds a new
  ADR and runs `vaultspec-core vault adr supersede OLD --by NEW` in the same session, so
  one record is `accepted` per decision.
- **Plan** (`.vault/plan/`) sequences the execution of one ADR or a cluster of ADRs.
  `related:` lists every governing ADR (`--related`, repeatable, at scaffold;
  `vaultspec-core vault link add` later). Scaffold with `--tier L1..L4`; build and
  change structure only through the `plan_progress` and `plan_edit` tools or the
  `vaultspec-core vault plan` verbs. Conventions are in the hint blocks of
  `.vaultspec/templates/plan.md`.
- **Ledger** (`.vault/exec/`) is the mechanical log of a plan's execution, one per plan,
  append-only.
  `vaultspec-core vault exec log --feature <feature> --step S## --related <plan-stem> --row A:path`
  (the `log` tool when connected) creates it on first use and appends one
  `S## A|M|D|R path` row per path touched; `--verify` adds a check line, `--by` the
  persona, `--note` an exception (data loss, skipped work, a scaffold left in code, a
  persistent failure). Rows are written only by the verb. No narrative.
- **Audit** (`.vault/audit/`) holds findings from review or curation, one
  `### {topic} | {level} | {summary}` entry each, appended as a rolling log, with
  recommendations that name a decision for a follow-on ADR rather than making it.
  Requires the artifacts it reviews.
- **Feature index** (`.vault/index/`) is generated: the `create` and `edit` tools
  regenerate it; after CLI scaffolds run `vaultspec-core vault feature index`.

A feature that needs a second ADR, audit, reference, or research record disambiguates it
with the owning verb's `--topic` flag, never a hand-picked filename.

## Links and boundaries

- `related:` carries quoted Obsidian wiki-links (`- '[[stem]]'`), set by the owning
  verbs. Bodies carry no wiki-links and no markdown links; a source file is named in
  backticks, a code fact is cited as `path:line`.
- Vault records cite code; code never cites the vault. The `Vaultspec-Step` and
  `Vaultspec-Feature` commit trailers (`vaultspec-core vault plan trailer emit`) are the
  only link from git history to a record; emit them when the project's recent commits
  already carry them.
- Each fact has one home: research grounds, the ADR decides, the plan sequences, the
  ledger logs, the audit finds. A fact needed elsewhere is cited by stem, not restated.
