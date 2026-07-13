---
tags:
  - '#adr'
  - '#placeholder-markdown-lints'
date: '2026-06-24'
modified: '2026-06-25'
related:
  - "[[2026-06-24-placeholder-markdown-lints-research]]"
---

# `placeholder-markdown-lints` adr: `lint and auto-fix template placeholders and markdown hygiene` | (**status:** `accepted`)

## Problem Statement

The framework rule (`vaultspec.builtin.md`) mandates that no document is committed
with `{...}` template placeholders remaining, yet no health check enforces it. An audit
of the rule against the check suite found that the only residue check, `annotations`,
strips `<!-- -->` scaffolding comments but never inspects body prose for unreplaced
placeholders. A stray `{topic}` in a heading, or an unresolved
`{proposed|accepted|rejected|deprecated}` enum in an ADR status line, sails through
`vault check all` today. Separately, the vault has no markdown hygiene check at all:
trailing whitespace, runs of blank lines, and missing or doubled final newlines
accumulate silently and produce noisy diffs.

This ADR adds two checks to close both gaps: a detection-only `placeholders` lint for
`{...}` residue, and a fixable `markdown` hygiene lint, both first-class members of the
suite on parity with `annotations`.

## Considerations

Every shipped template seeds `{...}` placeholders (`{feature}`, `{topic}`, `{title}`,
the `{proposed|accepted|rejected|deprecated}` enum, machine-filled `{step_id}` /
`{document_list}`, etc.), so the rule is real and load-bearing. The detection grammar
must distinguish a genuine placeholder from incidental brace usage in authored prose:
JSON or dict literals (`{ "key": 1 }`), regex quantifiers (`{4}`, `{2,4}`), and shell
expansions (`${VAR}`) all use braces but are not placeholders.

The grounding observation is that real placeholders share a tight grammar: lowercase
ASCII letters plus `0-9 _ - * |`, containing at least one letter, no spaces, quotes, or
colons. This admits every template placeholder while rejecting the incidental forms
above. Real placeholders also appear inside inline backticks in headings (the shipped
`` # `{feature}` plan `` form), so inline code spans on heading lines must be scanned, not
stripped - the opposite of `body-links`. On non-heading lines inline code is stripped,
because a backtick-wrapped placeholder in body prose is documentation, not residue.

## Constraints

Both checks depend only on the existing check contract
(`CheckResult` / `CheckDiagnostic` / `Severity` / `VaultSnapshot`) and the shared
`atomic_write` helper - no new libraries, no frontier risk. The `markdown` fixer must
honour the repository's newline-preservation discipline: read bytes, detect the source
CRLF/LF convention, and write bytes back so a CRLF file is never silently rewritten to
LF (the same constraint `frontmatter` and `annotations` already observe). The
`placeholders` lint is detection-only: an unreplaced placeholder marks missing author
or machine content that cannot be synthesised safely, so there is no auto-fill. This is
parity with `body-links`, which is also a detection-only suite member. The
comment-embedded placeholders are already handled - `annotations --fix` removes the
whole `<!-- -->` block, so the `placeholders` lint strips HTML comments before scanning
to avoid double-reporting that residue.

## Implementation

Two new modules under `vaultcore/checks/`, each exporting one checker function that
follows the established signature and is wired into `run_all_checks`, the
`checks/__init__` re-exports, and a `vault check` CLI subcommand.

`check_placeholders` scans body prose (everything after the frontmatter) for the
placeholder grammar after stripping HTML comments and fenced code blocks but preserving
inline code spans, with a `$` lookbehind. Each hit is an `ERROR`; a match containing `|`
is reported as a "choose one option" enum rather than a missing value. Frontmatter is
out of scope because leftover frontmatter placeholders already fail the `frontmatter`
date and tag validators; scanning it would double-report.

`check_markdown` detects and, under `--fix`, repairs three safe hygiene lints aligned
with the markdownlint rules MD009 (trailing whitespace), MD012 (consecutive blank
lines collapsed to one), and MD047 (file ends in exactly one newline). Findings are
`WARNING`; the fixer preserves the source newline convention and writes atomically. It
runs after `annotations` in the suite so blank lines left by stripped comments are
collapsed in the same pass.

## Rationale

The grammar-plus-context approach was chosen over a naive `\{.*?\}` scan because the
vault corpus contains legitimate brace usage; a naive scan would be unusable from false
positives. Detection-only placeholders plus a fixable markdown hygiene check matches the
existing split in the suite (`body-links` detects, `annotations` fixes) and keeps each
check's responsibility single. The markdownlint rule numbers anchor the hygiene lints to
a well-known external standard rather than ad-hoc choices.

## Consequences

`vault check all` now enforces the placeholder rule the framework already documents, and
`--fix` cleans whitespace and blank-line noise that previously surfaced only in review
diffs. The placeholder lint has a known, accepted limitation: a placeholder-shaped token
deliberately written in inline backticks in authored prose (e.g. documenting a format
string as `` `{name}` ``) is flagged; this is rare in the prose corpus and preferable to
missing real residue. The markdown fixer deliberately omits riskier transforms (tab
conversion, reflowing, heading spacing) to stay strictly safe and idempotent.

## Codification candidates
