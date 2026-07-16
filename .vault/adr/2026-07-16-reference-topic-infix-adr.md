---
tags:
  - '#adr'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-reference-topic-infix-research]]"
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-27-rename-convergence-adr]]'
  - '[[2026-07-09-mcp-tool-schema-adr]]'
---

# `reference-topic-infix` adr: `topic-infix scaffolding for the narrative document trio` | (**status:** `accepted`)

## Problem Statement

A feature's second reference, research, or audit document has no route through the
owning scaffolder: the filename builder always resolves
`{date}-{feature}-{type}.md`, collides with the first document, and forces
hand-authored frontmatter - the exact violation the owning-verb mandate exists to
prevent (GitHub issue 205; grounded in
`2026-07-16-reference-topic-infix-research`). The audit infix convention decided by
the firmware-wording-review record is documented but unimplemented. The decision:
which document types admit a topic infix, through which surfaces, with what
validation.

## Considerations

- The grounding research establishes: one structural collision site in the filename
  builder; validators and real corpora already accept infixed filenames; the change
  surface is the filename builder, the CLI flag set, the MCP create tool, and the
  firmware filename patterns plus the generated CLI reference.
- Standing cardinality rules exclude adr and plan from disambiguation-by-infix
  (amend-or-supersede; one plan per decision cluster), and exec filenames are
  machine-derived from plan identifiers.
- `vault feature rename` refuses narrative-filename features (rename-convergence
  decision, open follow-on); an infix flag grows that population but does not create
  the condition.
- Both CLI and MCP transports must converge on the same owning-verb logic per the
  mcp-tool-schema decision; a CLI-only flag would fork the surfaces.

## Considered options

- **Infix for the narrative trio only - audit, reference, research (chosen).**
  Matches the documented audit convention, answers the issue, and respects the adr,
  plan, and exec cardinality rules.
- **Infix for all doc types.** Rejected: invites sibling ADRs and fragmented plans,
  contradicting two standing decisions.
- **Reference-only (issue minimum).** Rejected: leaves audit's documented convention
  unimplemented and research inconsistent for no saved complexity; the builder change
  is type-agnostic either way.
- **Overload --title to also drive the filename.** Rejected: title is narrative prose
  with unconstrained characters; filenames need the kebab-case identifier discipline,
  and silently coupling the two changes existing behavior.

## Constraints

- The topic value is validated kebab-case through the shared normalizer
  (`normalize_feature_tag` with a topic label), the same validator the feature tag
  uses on both transports.
- `--topic` on a non-admitting doc type is a hard error, mirroring the existing
  step-flag validation pattern in the add command.
- Omitted topic preserves today's filename exactly (backward compatible); the
  existing exists- and stem-collision guards stay in force on the infixed path.
- The MCP `create` tool gains the same optional field converging on the same
  `create_vault_doc` call; the tool-schema decision's owning-verb invariant is
  untouched.
- The generated CLI reference must be regenerated and its drift test stay green.

## Implementation

`create_vault_doc` gains an optional `topic` parameter; when set on an admitting doc
type the filename resolves to `{date}-{feature}-{topic}-{type}.md`, otherwise
behavior is byte-identical to today. The CLI `vault add` gains `--topic` with
normalization and the non-admitting-type error; the MCP `DocumentSpec` gains the
matching optional field. The vaultspec rule's file-name patterns and document list
name the infix form for audit, reference, and research (audit already documented);
the CLI reference regenerates via the reference generator. Unit tests cover the
infixed filename for each admitting type, the omitted-topic fallback, the
non-admitting-type error, topic normalization, and collision behavior between two
different topics (allowed) and duplicate topics (refused).

## Rationale

The narrative-trio scope is the only option consistent with all standing decisions
at once: it implements the convention the firmware already documents, closes the
issue's owning-verb violation for reference and research, and declines to hand adr
and plan a disambiguation mechanism their cardinality rules forbid. Routing the flag
through the shared normalizer and the single filename builder keeps one
identifier-discipline authority and one collision authority, and adding the field on
both transports keeps the CLI and MCP surfaces converged per the tool-schema
decision.

## Consequences

Good: second documents scaffold through the owning verb with machine-owned
frontmatter; the documented audit convention becomes real; downstream vaults stop
hand-mirroring filenames. Bad: the narrative-filename population grows, enlarging the
known `vault feature rename` refusal class until that follow-on is decided; one more
optional flag on an already wide add command. Neutral: omitted-topic behavior is
byte-identical; adr, plan, and exec are untouched; the infix remains optional
disambiguation, never required.

## Codification candidates

- **Rule slug:** `narrative-infix-owning-verb`.
  **Rule:** A second audit, reference, or research document for a feature is
  scaffolded with the owning verb's topic infix
  (`{date}-{feature}-{topic}-{type}.md`), never by hand-writing a filename; adr,
  plan, and exec documents never take an infix.
