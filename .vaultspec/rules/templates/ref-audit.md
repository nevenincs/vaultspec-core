---
tags:
  - '#reference'
  - '#{feature}'
date: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     Required tags: one directory tag and one feature tag.
     Directory tag is hardcoded as #reference for .vault/reference/ documents.
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

# `{feature}` reference: `{topic}`

Brief description of what was researched and what sources were consulted.

Include any concrete references to files, line numbers, modules, etc. This is
the information that coding agents will consult during implementation.

## Findings

Findings pertinent to `{feature}` being considered. Include implementation
details and architecture overviews considered insightful, essential, or
relevant. Adapt format to content.
