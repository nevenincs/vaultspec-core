---
name: vaultspec-research
description: Explore an unfamiliar problem and weigh options before committing. Use when unsure how to approach a complex feature, refactor, or bug.
---

# Research and brainstorm skill (vaultspec-research)

Use this skill:

- Before implementing non-trivial features.
- When unsure about major design decisions.
- Before refactors with unclear scope.
- Before debugging complex issues.
- When you need user input on design options.

**Announce at start:** "I'm using the `vaultspec-research` skill to conduct structured
research and brainstorming."

## Required steps

- **Ground in existing intent first.** Begin by grounding via semantic search - the
  fastest, cheapest way to surface what the project already decided and built. Follow
  the validated sequence: locate, read whole, confirm. Retrieve governing decisions with
  `vaultspec-rag search "<intent>" --type vault --doc-type adr` (the directed ADR
  filter, sharper than catch-all `--type vault`), prior exploration with
  `vaultspec-rag search "<intent>" --type vault` (or `--doc-type research`), and the
  implementation sites with `vaultspec-rag search "<intent>" --type code`. Lean on
  `vaultspec-core status` and `vaultspec-core vault list` - first-class for orientation
  \- to map in-flight plans and records. Read what this surfaces in full and check for
  overlap before adding new findings; round out decision recall by listing `.vault/adr/`
  and filtering by feature. Where `vaultspec-rag` is not installed, the `vaultspec-core`
  discovery verbs and grep carry the same sequence.

- **Read and use the template** at `.vaultspec/templates/research.md`; its embedded hint
  blocks govern the body structure: an answer-first lead paragraph, claim-first
  `## Findings` subsections, and a closing `## Sources` section.

- **Load the `vaultspec-adr-researcher` agent persona** for focused work. When the task
  benefits from multiple researchers, load the generic `vaultspec-researcher` agent
  persona for the additional research threads and coordinate them through the host
  environment. Instruct each researcher to "Conduct research on `{topic}`." and write
  the returned findings into the scaffolded document's body.

- **Persist findings:** scaffold the research artifact with
  `vaultspec-core vault add research --feature {feature}`, then author the findings as
  body prose in the scaffolded file. The CLI owns the filename
  (`.vault/research/yyyy-mm-dd-{feature}-research.md`) and the frontmatter; never
  hand-write either. The full frontmatter schema is defined in the `vaultspec` rule;
  verify after scaffolding with `vaultspec-core vault check all` rather than
  hand-editing frontmatter. A scaffold left with its hint text, an unfilled `{topic}`,
  or an empty Findings section is not research - fill every section in the same session
  or do not create the document.

- **Persist sources:** every finding's source is a re-fetchable locator (URL,
  `file:line`, commit SHA, `package@version`, RFC number), cited inline and collected
  once in the closing `## Sources` section; ground code in a `<Reference>` via
  `vaultspec-code-research` and link it.

## Quality gate

Judged by decision value per token; agents re-read the artifact in every later phase.
Before persisting, hold the document to this bar:

- **Answer-first.** Lead states question, stakes, and conclusion; each finding opens
  with its claim, evidence after.
- **Locator-anchored.** Every non-obvious claim carries a re-fetchable locator; an
  unanchored claim is marked as opinion.
- **Comparative.** Alternatives named, with why each was kept or rejected.
- **Specific.** Versions, dates, and numbers pinned; never "popular" or "widely used."
- **Deduplicated.** Each fact stated once. What a related vault document already records
  is linked, not restated; what an earlier section establishes is not repeated.
- **Grounding, not deciding.** Frame options, evidence, and trade-offs; at most name the
  option the evidence favors and what the `<ADR>` must settle. Decisions are recorded
  only in the `<ADR>`.
- **Bounded.** Uninvestigated areas stated; unverified general-knowledge claims flagged.
- **Lean.** Link, do not copy; no hedging boilerplate, no restated prompt, no closing
  summary.

Dispatched researcher findings meet the same bar; transfer them into the scaffolded body
without diluting the locators.

## Workflow

Research is the upstream precursor for a feature: it produces `<Research>` grounding for
a decision, not an implementation. From here the work branches:

- **Forward to the decision** -> on user approval, proceed with the `vaultspec-adr`
  skill to create and persist the `<ADR>` the research supports.

- **Out to grounding** -> when the decision needs grounding in real source code,
  reference implementations, or library docs, branch to the `vaultspec-code-research`
  skill (which can dispatch the `vaultspec-reference-auditor` agent) to produce a
  `<Reference>`, then fold its findings back into the research or ADR.

- **Back to refinement** -> without approval, prompt the user to refine goal and
  constraints, then re-run research.

## Artifact linking

- Persisted documents reference each other with quoted `'[[wiki-links]]'` in the
  `related:` frontmatter field.
- DO NOT use `@ref` style links.
- DO NOT use `[label](path)` style links for internal wiki pages.
