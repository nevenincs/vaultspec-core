---
tags:
  - '#adr'
  - '#{feature}'
date: '{yyyy-mm-dd}'
modified: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `{feature}` adr: `{title}` | (**status:** `{proposed|accepted|rejected|deprecated}`)

## Problem Statement

<!-- Briefly describe the architectural problem or concern.
Describe why the ADR is being persisted. Is this a new feature? Result of an audit? -->

## Considerations

<!-- Key factors, constraints, requirements. Tech/libraries considered. -->

## Constraints

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

<!-- Brief rationale why architecture decision was made. Reference `{research}` findings and grounding `{reference}`. -->

## Consequences

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
