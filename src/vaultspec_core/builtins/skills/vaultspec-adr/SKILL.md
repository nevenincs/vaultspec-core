---
name: vaultspec-adr
description: Capture an architectural decision as an ADR in .vault/adr/. Use after research, before planning, when a significant design choice and its trade-offs must be recorded.
---

# ADR writing skill (vaultspec-adr)

Use this skill:

- After a `vaultspec-research` session has concluded with a recommendation.
- When multiple competing technical choices need a grounding document.
- When a significant architectural decision is made that affects the project's
  foundations, feature set, or development trajectory.
- To document the blast radius, "why", and "what" of major architectural choices.
- When an accepted decision needs refining or concretizing - this amends the existing
  record in place, not a new document (see Amend or supersede).

**Announce at start:** "I'm using the `vaultspec-adr` skill to create a new ADR."

## Required steps

- **Ground the decision in existing intent first.** Before drafting, retrieve the prior
  decisions that bind this area - the surest way to architect on top of them rather than
  silently contradicting them. Lead with
  `vaultspec-rag search "<intent>" --type vault --doc-type adr` (the directed ADR
  filter, sharper than catch-all `--type vault`); read each in full - a record already
  governing this scope routes through Amend or supersede below. Use
  `vaultspec-rag search "<intent>" --type code` for the implementation sites the
  decision will touch, then confirm exact symbols with grep, and lean on
  `vaultspec-core status` and `vaultspec-core vault list` - first-class for orientation
  \- to map related records. Round out decision recall by listing `.vault/adr/` and
  filtering by feature - search can miss lower-ranked or opaquely-named records. Where
  `vaultspec-rag` is not installed, the `vaultspec-core` discovery verbs and grep carry
  the same sequence.

- **Read and use the template** at `.vaultspec/templates/adr.md`; its embedded hint
  blocks govern the body structure.

- **Scaffold via the CLI:**
  `vaultspec-core vault add adr --feature {feature} --related <research-stem>`, then
  author the body prose in the scaffolded file. The CLI owns the filename
  (`.vault/adr/yyyy-mm-dd-{feature}-adr.md`) and the frontmatter; never hand-write
  either. The full frontmatter schema is defined in the `vaultspec` rule; verify after
  scaffolding with `vaultspec-core vault check all` rather than hand-editing
  frontmatter.

- **Read and link related Research from:**
  `.vault/research/yyyy-mm-dd-{feature}-research.md`.

- **Terminate if related research is not found** and prompt the user to first invoke
  `vaultspec-research`.

## Amend or supersede

One decision, one governing record. The grounding step surfaces the ADRs that already
govern this scope; when one exists, choose the mode before touching anything:

- **Amend (the default).** Refinement, concretization, narrowed scope, an
  implementation-driven parameter change: rewrite the existing record's body in place,
  with the same user approval a new ADR would need. Status stays `accepted`; the
  `modified:` stamp carries the revision. No new document.
- **Supersede (pivot only).** The decision reverses direction, or the record's rationale
  no longer supports the new choice: scaffold the new ADR and in the same session run
  `vaultspec-core vault adr supersede OLD --by NEW`, so exactly one record is `accepted`
  for the scope.

Refinement-by-new-document is the failure mode this rule exists to stop: it piles
sibling ADRs onto one decision until the cluster carries mutually contradictory
`accepted` markers and the supersession chain, not the decision, becomes the thing being
managed.

## Document boundary

Each fact has one home: the research grounds, the ADR decides. The record cites research
and reference findings by stem (e.g. `2026-02-04-editor-demo-research`) and never
restates their evidence - a restated fact forks, bloats agent context, and goes stale
silently. If drafting surfaces a fact the grounding lacks, add it to the research or
`<Reference>` first, then cite it. Conversely, the decision lives only here: strip any
decision language the grounding documents carry into this record rather than duplicating
it.

## Workflow

- **Derive from Research:** ADRs should always be preceded by a `vaultspec-research`
  session.

- **CRITICAL: you MUST always** present ADR findings as an interactive prompt for user
  approval. Without explicit user sign-off the ADR is considered null and void.

- **Draft the ADR using the `vaultspec-adr-researcher` agent persona**, which formalizes
  the research-backed decisions into ADR content and returns it for persistence into the
  scaffolded document (the `vaultspec-writer` persona's mandate is plan-only).

- Associate the ADR with `{feature}` based on the findings in `[[...-research.md]]`.

- **Supersession mechanics:** `vaultspec-core vault adr supersede OLD --by NEW` records
  the `superseded_by:` back-pointer and rewrites the old record's status; never edit
  status lines by hand.

- **Linking:** Use `[[wiki-links]]` for references. DO NOT use `@ref` or
  `[label](path)`.
