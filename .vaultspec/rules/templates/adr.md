---
tags:
  - '#adr'
  - '#{feature}'
date: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     Required tags: one directory tag and one feature tag.
     Directory tag is hardcoded as #adr for .vault/adr/ documents.
     Replace {feature} with a kebab-case feature tag, e.g. #editor-demo.
     Additional tags may be appended below the required pair.
     Date must use ISO format, e.g. 2026-02-06.
     Related documents must be quoted wiki-links, e.g.
     "[[2026-02-04-feature-research]]". -->

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `{feature}` adr: `{title}` | (**status:** `{accepted|rejected|deprecated}`)

## Problem Statement

Briefly describe the architectural problem or concern.

## Considerations

Key factors, constraints, requirements. Tech/libraries considered.

## Constraints

Technical limitations, time constraints, etc.

## Implementation

High-level description of HOW it will be implemented. Reference `{research}`
and `{reference}` specs.

## Rationale

Why this option was chosen. Reference `{research}` findings and external
`{reference}` patterns.

## Consequences

Difficulties, implementation consequences, future considerations.
