---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/exec/ location)
# Feature tag (replace {feature} with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#exec'
  - '#{feature}'
# ISO date format (e.g., 2026-02-06)
date: '{yyyy-mm-dd}'
# Originating Step's canonical identifier (S##) from the plan.
# Required: machine-readable linkage from this Step Record back
# to the Step row in the parent plan document.
step_id: '{S##}'
# Related documents as quoted wiki-links - MUST link to parent PLAN
# (e.g., "[[2026-02-04-feature-plan]]")
related:
  - '[[{yyyy-mm-dd-*-plan}]]'
---

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

# `{feature}` `{phase}` `{step}`

Brief summary of work done.

- Modified: `{file1}`
- Created: `{file2}`

## Description

Detailed description of implementation details.

## Tests

Brief description of tests and validation results.
Link any audit reports related to `{phase}` or `{step}`.
