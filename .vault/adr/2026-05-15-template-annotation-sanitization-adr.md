---
tags:
  - '#adr'
  - '#template-annotation-sanitization'
date: '2026-05-15'
related:
  - '[[2026-05-15-template-annotation-sanitization-research]]'
---

# template-annotation-sanitization adr: explicit generated annotation sanitation | status: accepted

## Problem Statement

VaultSpec templates contain instructions for agents, but generated vault
documents can retain those instructions after authors fill out the scaffold.
The current templates also mix YAML `# ...` comments with Markdown HTML comments,
which makes it harder to distinguish template guidance from real document
content.

## Considerations

Template hydration must preserve guidance because agents rely on it when a new
document is created.

Sanitization must be explicit and operator-controlled. It belongs in fix and
repair paths, not in the creation path.

The sanitizer must preserve non-template machine state, especially the
`<!-- RETIRED: ... -->` plan identifier ledger.

The command surface must be visible across direct checks, explicit sanitation,
repair, pre-commit, and local development fix recipes.

## Constraints

The change must not introduce mocks or shadow template logic in tests.

The source templates must remain readable to agents.

The sanitizer must preserve line endings when it rewrites a document.

Existing body-link checks ignore HTML comments, so annotation sanitation needs
its own check rather than extending link validation.

## Implementation

Add an `annotations` vault checker that reports generated template annotations
as fixable warnings and strips them only when requested.

Register the checker in `vault check all`, expose
`vault check annotations --fix`, and add `vault sanitize annotations` as the
explicit command.

Run the same checker inside `vault repair` through the shared check suite.

Add a canonical pre-commit hook and dev fix recipe entry for
`vault sanitize annotations`.

Move template frontmatter guidance out of YAML `# ...` comments and into
Markdown comment directives after frontmatter.

## Rationale

This keeps the document creation lifecycle intact: generated templates still
carry instructions for the agent filling them out. Operators get a clear,
repeatable sanitation path when they decide the document is ready for cleanup.

Making sanitation a checker keeps dry-run planning, JSON diagnostics, repair,
and pre-commit behavior consistent with the rest of VaultSpec's maintenance
model.

## Consequences

Newly generated vault documents still include template annotations until an
operator runs the sanitizer or a fix pipeline.

Historical vault documents can be cleaned by running the explicit sanitizer.

Pre-commit can now remove generated annotations before commit, so operators
should expect staged vault documents to change when annotation guidance remains.
