---
tags:
  - '#audit'
  - '#{feature}'
date: '{yyyy-mm-dd}'
modified: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `{feature}` code review

<!-- Persistent log of audit findings appended below. -->

<!-- FINDINGS FORMAT:
     Append one section per finding using the heading form
     ## {topic}-### | {level} | {summary}
     followed by a body paragraph carrying the {description}.
     {topic} is a concise kebab-case slug, {level} is the severity
     (critical, high, medium, low), and {summary} is a one-line statement. -->
