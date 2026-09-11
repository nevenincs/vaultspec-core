---
name: vaultspec-code-research
description: Ground a coding task in real source code, reference implementations, and library docs. Use before implementing a complex feature or when documentation is thin.
---

# Code research skill (vaultspec-code-research)

Use this skill:

- When auditing, researching, or implementing a specific technical implementation.
- When you need to identify a reference project.
- When you need source references that show how another project implements a feature.
- To avoid missing implementation details.
- To ground and de-risk complex coding tasks with actual code.

Invoke when the `vaultspec-research` -> `vaultspec-adr` -> `vaultspec-write` flow
explicitly requires direct code referencing.

**Announce at start:** "I'm using the `vaultspec-code-research` skill to find out how
`{Reference}` implements `{Feature}`."

## Required steps

- **Ground in existing intent first.** Lead the code deep dive with semantic search:
  `vaultspec-rag search "<intent>" --type code` locates the semantically matching
  implementation sites - read the epicenter or nearest analogue in full, then confirm
  exact symbols with a targeted grep, which is sharper at exact-symbol lookup. Retrieve
  the governing decisions with
  `vaultspec-rag search "<intent>" --type vault --doc-type adr` (the directed ADR
  filter, sharper than catch-all `--type vault`) to anchor the audit. Where
  `vaultspec-rag` is not installed, the `vaultspec-core` discovery verbs and grep carry
  the same sequence.

- **Read and use the template** at `.vaultspec/templates/reference.md`; its embedded
  hint blocks govern the body structure.

- **Load the `vaultspec-reference-auditor` agent persona** for the focused code deep
  dives. Instruct it to locate and audit the `{Feature}` implementation in the reference
  codebase; it returns its findings to you for persistence.

- **Persist findings:** scaffold the reference document with
  `vaultspec-core vault add reference --feature {feature}`, then author the findings as
  body prose. The CLI owns the filename
  (`.vault/reference/yyyy-mm-dd-{feature}-reference.md`) and the frontmatter; never
  hand-write either. The full frontmatter schema is defined in the `vaultspec` rule;
  verify after scaffolding with `vaultspec-core vault check all` rather than
  hand-editing frontmatter.

## Research and audit

Perform focused code deep dives.

Coordinate the loaded persona and any supporting agents to:

- Locate the code snippets and files.
- Analyze implementation patterns and architecture.
- Persist a Reference blueprint into the scaffolded document's body. If the document
  exists already, assess and update its body prose.

## Implementation plan

You MUST check if an implementation exists already. If it does:

- Do our findings alter the implementation? If so, report back to the user.
- Report possible issues or drift and leave notes in the Plan that reference the
  `{Feature}` audit.
