---
tags:
  - '#exec'
  - '#{feature}'
date: '{yyyy-mm-dd}'
step_id: '{S##}'
related:
  - '[[{yyyy-mm-dd-*-plan}]]'
---

<!-- FRONTMATTER RULES:
     Required tags: one directory tag and one feature tag.
     Directory tag is hardcoded as #exec for .vault/exec/ documents.
     Replace {feature} with a kebab-case feature tag, e.g. #editor-demo.
     Additional tags may be appended below the required pair.
     Date must use ISO format, e.g. 2026-02-06.
     step_id is the originating Step's canonical identifier, e.g. S01.
     Related documents must be quoted wiki-links and must link to the
     parent plan, e.g. "[[2026-02-04-feature-plan]]". -->

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `{feature}` `<display-path>`

<!-- The <display-path> in the heading above is the originating Step's
     tier-conditional display path:
       L1       = `{step}`            (e.g., `S01`)
       L2       = `{phase}.{step}`    (e.g., `P01.S01`)
       L3 / L4  = `{wave}.{phase}.{step}`  (e.g., `W01.P01.S01`) -->

Brief summary of work done.

- Modified: `{file1}`
- Created: `{file2}`

## Description

Detailed description of implementation details.

## Tests

Brief description of tests and validation results.
Link any audit reports related to `{phase}` or `{step}`.
