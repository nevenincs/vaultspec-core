---
tags:
  - '#adr'
  - '#{feature}'
date: '{yyyy-mm-dd}'
modified: '{yyyy-mm-dd}'
body_schema: 'body-v1'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Reuse, amendment, and supersession follow the vaultspec system section.
     Preserve accepted content while a revision is pending; apply only an
     authorized amendment. Accept a reversal's successor before superseding
     its predecessor. Unchanged coverage needs no new record.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `{feature}` adr: `{title}` | (**status:** `{proposed|accepted|rejected|superseded|deprecated}`)

<!-- DOCUMENT BOUNDARY:
     Keep the ruling understandable on its own: scope, commitment, rationale,
     consequences. Cite detailed research/reference/audit evidence by stem.
     Each section may be a sentence; do not pad it to resemble a specification.
     Inconclusive experiments remain evidence, not an accepted decision. -->

## Problem Statement

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

<!-- Binding commitments and scope, including exceptions and affected prior rulings.
     Make obligations distinguishable from implementation hypotheses. -->

## Implementation

<!-- Lead with the chosen decision: "We will ..." and its scope. Follow with only the
     implementation outline needed to understand it. Mark hypotheses that may change
     within the constraints; keep task sequencing and code elsewhere. -->

## Rationale

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

<!-- Benefits, accepted costs, and conditions that would require reconsideration.
     Acceptance does not assert that implementation is already complete. -->
