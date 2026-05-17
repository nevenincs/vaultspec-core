---
tags:
  - '#research'
  - '#cli-memory-lifecycle'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-memory-lifecycle` research: `Memory-lifecycle gap: findings synthesis`

Synthesis note. Distils the audit's three rounds of evidence on a
single axis — the verbs the CLI offers for mutating the project's
durable memory — and identifies the architectural shape the sibling
ADR proposes.

## Findings

### The structural model holds; the verbs that mutate it do not

Round 3b S18 (positive) confirmed that the frontmatter + wiki-links
+ feature-index model handles parallel features cleanly. Two
features authored same-day with cross-feature `related:` links
produced no collisions and no cross-talk at the leaf level. The
representation layer is sound.

The failure surface is the set of CLI verbs that change memory
state across the lifecycle:

- **Codification** verb does not exist. Pipeline ends at `audit`;
  durable rules do not get authored from findings unless an agent
  is explicitly prompted (round 3a Bridge Gap).
- **Supersession** verb does not exist (B3). Override has to be
  reconstructed from prose plus flat `related:` plus emergent
  feature-index rendering.
- **Retirement** verb exists but actively destroys provenance (B9
  critical). `vault feature archive` is structurally broken across
  five compounding dimensions: no preview, no reversal, breaks
  cross-feature links, writes an illegal directory, auto-fix
  amputates relationships.

Three points on one axis, three different failure modes, one shared
cause: the framework was built bottom-up from the representation
layer without an architectural pass over the verbs that move state
through the lifecycle.

### What the existing model already offers

- `related:` is a flat list of wiki-link references. It cannot
  distinguish "supersedes" from "informs" from "authorised-by".
- Feature indexes regenerate from each document's H1 line. The H1
  status token is the only place where override is visible today,
  and that visibility is accidental.
- Frontmatter is extensible (schema validated by the schema check)
  and migration-aware via the migrations registry.
- Per-feature isolation works. A new feature tag is sufficient to
  carve a new memory namespace.

### What is missing from the existing model

- Typed relationship fields beyond flat `related:`.
- A documented status taxonomy in ADR frontmatter beyond the
  freeform body-prose status token.
- A reverse-pointer mechanism. An ADR knows it has been superseded
  only by another document advertising it, not by carrying that
  fact in its own frontmatter.
- An archive-aware link resolver.
- A pipeline phase that follows review.

### Vocabulary work the lifecycle verbs need to do

Three CLI verbs map cleanly to natural English: `codify`,
`supersede`, `retire`. They sit alongside the existing pipeline
verbs (`research`, `decide`, `plan`, `execute`, `review`) and form
the lifecycle's third triple — what happens after a feature is
done. The current CLI has no answer to that question.

## Constraints identified

- Frontmatter schema changes need a versioned migration entry.
- The feature-index renderer must keep rendering correctly through
  any change in supersession semantics — it is the system's
  accidental source of truth for override today and removing that
  property silently would break existing audits.
- Cross-feature `related:` links must survive `archive` in
  resolvable form. This determines whether archive is a move
  (today, broken) or a tag (rejected — defeats the visual purpose).

## Recommendation

The sibling ADR proposes three first-class CLI verbs (one per
lifecycle endpoint), four new frontmatter relationship fields, and
companion language updates to the ADR template, pipeline rules,
and agent personas.
