---
tags:
  - '#exec'
  - '#{feature}'
date: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*-plan}]]'
---

<!-- FRONTMATTER RULES:
     Required tags: one directory tag and one feature tag.
     Directory tag is hardcoded as #exec for .vault/exec/ documents.
     Replace {feature} with a kebab-case feature tag, e.g. #editor-demo.
     Additional tags may be appended below the required pair.
     Date must use ISO format, e.g. 2026-02-06.
     Related documents must be quoted wiki-links and must link to the
     parent plan, e.g. "[[2026-02-04-feature-plan]]". -->

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- PHASE SUMMARY:
     This file rolls up every <Step Record> belonging to one Phase
     of the originating plan. Each Step (S##) in the Phase produces
     one <Step Record> in `.vault/exec/`; this summary aggregates
     them, lists modified / created files across the Phase, and
     reports verification status. -->

# `{feature}` `{phase}` summary

Brief summary of overall progress across every Step in this Phase.

- Modified: `{file1}`
- Created: `{file2}`

## Description

High-level description of work accomplished.

## Tests

Brief description of overall verification and auditing.

Link any audit reports related to `{phase}` summary or individual
`{step}` summaries.
