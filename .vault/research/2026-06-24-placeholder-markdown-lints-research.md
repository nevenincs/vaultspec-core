---
tags:
  - '#research'
  - '#placeholder-markdown-lints'
date: '2026-06-24'
modified: '2026-06-25'
related: []
---

# `placeholder-markdown-lints` research: `template placeholder and markdown hygiene lints`

A prose audit of the framework rule `vaultspec.builtin.md` against the live check suite
surfaced a gap between a documented rule and its enforcement, plus a missing hygiene
layer. This note records what the templates seed, what the suite already covers, and the
grammar that separates a real placeholder from incidental brace usage.

## Findings

### The placeholder rule is real but unenforced

Every shipped template under `builtins/templates/` seeds `{...}` placeholders. A scan
counts these classes: frontmatter (`{feature}`, `{yyyy-mm-dd}`, `{yyyy-mm-dd-*}`,
`{tier}`); machine-filled (`{step_id}`, `{plan_stem}`, `{heading}`, `{scope_block}`,
`{document_list}`); author narrative (`{topic}`, `{title}`, `{phase}`, `{summary}`,
`{level}`, `{description}`, `{file1}`, `{file2}`, cross-ref stems `{research}`,
`{reference}`, `{adr}`); and one enum, `{proposed|accepted|rejected|deprecated}`, in the
ADR status H1. The rule "no template committed with `{...}` remaining" is therefore
load-bearing, but no check inspects body prose for residue.

### Existing coverage and the overlap boundary

The `frontmatter` check rejects placeholder-shaped tags and dates (a literal
`#{feature}` fails the kebab-case feature-tag rule; `{yyyy-mm-dd}` fails the date
format), so frontmatter placeholders are already covered. The `annotations` check strips
`<!-- -->` blocks, which removes the placeholders that live inside template guidance
comments. The uncovered surface is therefore exactly body prose outside comments -
headings and visible text - which is where the new `placeholders` lint must operate, and
why it strips HTML comments first to avoid double-reporting annotations residue.

### Placeholder grammar versus incidental braces

Real placeholders share a tight grammar: lowercase ASCII letters plus `0-9 _ - * |`,
with at least one letter, and no spaces, quotes, or colons. This admits every template
placeholder above while rejecting JSON or dict literals (`{ "key": 1 }`, spaces and
colons), regex quantifiers (`{4}`, `{2,4}`, no letter), and shell expansions
(`${VAR}`, excluded by a `$` lookbehind). Because the shipped heading form wraps the
placeholder in inline backticks (`` # `{feature}` plan ``), inline code spans must be
scanned rather than stripped - the inverse of the `body-links` policy - while fenced
code blocks are stripped to spare multi-line JSON and shell examples.

### Markdown hygiene has no check

The suite has no markdown hygiene lint. The safe, idempotent, auto-fixable subset maps
to markdownlint MD009 (trailing whitespace), MD012 (consecutive blank lines), and MD047
(single trailing newline). Riskier transforms (tab conversion, reflow, heading spacing)
are deliberately excluded to keep `--fix` strictly safe.
