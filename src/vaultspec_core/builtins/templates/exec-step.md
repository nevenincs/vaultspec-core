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
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

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

<!-- Headline summary of work done. Use:

- Agent: <your agent model, effort level>
- Session id: the session id of the agent, if available.

- Modified: `{file1}`
- Modified: `{file2}`
- Created: `{file3}` -->

## Description

<!-- Succint line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
