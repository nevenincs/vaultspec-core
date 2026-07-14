---
tags:
  - '#research'
  - '#{feature}'
date: '{yyyy-mm-dd}'
modified: '{yyyy-mm-dd}'
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

# `{feature}` research: `{topic}`

<!-- Lead paragraph: the question researched, why it matters to `{feature}`,
     and the answer or recommendation stated up front. A reader who stops
     here learns what was concluded, not merely what was attempted. -->

## Findings

<!-- One ### subsection per line of inquiry. Claim first: open each finding
     with its conclusion, follow with the minimal evidence that supports it,
     and anchor every non-obvious claim to a re-fetchable locator (URL,
     `file:line`, commit SHA, `package@version`, RFC number).
     Density rules: link, do not copy - never paste excerpts a reader can
     re-fetch; pin versions, dates, and numbers instead of "popular" or
     "widely used"; cut anything that changes no downstream decision; no
     hedging filler, no restated prompt, no closing summary repeating the
     body. Name the alternatives weighed and why each was kept or rejected,
     and state what was not investigated. -->

## Sources

<!-- Every locator cited above, collected and re-fetchable: code as
     `path:line` backtick locators, external references as bare URLs.
     Mark claims taken from general knowledge and not re-verified. -->
