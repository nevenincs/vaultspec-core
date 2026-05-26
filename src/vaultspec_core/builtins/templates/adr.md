---
tags:
  - '#adr'
  - '#{feature}'
date: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `{feature}` adr: `{title}` | (**status:** `{accepted|rejected|deprecated}`)

## Problem Statement

<!-- Briefly describe the architectural problem or concern.
Describe why the ADR is being persisted. Is this a new feature? Result of an audit? -->

## Considerations

<!-- Key factors, constraints, requirements. Tech/libraries considered. -->

## Constraints

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constrainst, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condense but clear prose that describes functionality layering.

Do not add code (code references must be persisted in separate `{reference}` document. Important `{reference}` snippets must be summarised and referenced explicitly. -->

## Rationale

<!-- Brief rationale why architecture descision was made. Reference `{research}` findings and grounding `{reference}`. -->

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
