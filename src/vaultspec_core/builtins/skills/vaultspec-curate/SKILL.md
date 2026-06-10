---
name: vaultspec-curate
description: >-
  Use this skill to audit and clean the .vault/ documentation vault. Validates frontmatter,
  wiki-links, naming conventions, template compliance, and directory
  structure. Fixes violations through the CLI repair paths and produces an
  audit report.
---

# Documentation Curation Skill (vaultspec-curate)

This skill governs the autonomous auditing and maintenance of the `.vault/`
documentation vault. It ensures every artifact conforms to the project's documentation
standards as defined in `.vaultspec/rules/rules/vaultspec.builtin.md`.

**Announce at start:** "I'm using the `vaultspec-curate` skill to audit and clean the
documentation vault."

## When to Use

- After completing a feature (post `vaultspec-execute`) to verify documentation trail
  integrity.

- Periodically as vault hygiene maintenance.

- When broken links, missing frontmatter, or organizational drift is suspected.

- Before onboarding a new feature to ensure the vault baseline is clean.

## Workflow

### Dispatch the Curator

Load the `vaultspec-docs-curator` agent persona. Instruct it to "Perform a full vault
audit of `.vault/`. Validate frontmatter, wiki-links, naming conventions, template
compliance, and directory structure. Repair violations through
`vaultspec-core vault check all --fix` and the CLI repair paths rather than hand edits,
and produce an audit report."

The curator's operating mode is **Audit -> Delegate -> Verify**: it identifies
violations with precision and orchestrates fixes through the CLI fix paths and loaded
agent personas rather than editing documents in-place itself, then re-scans after every
delegated repair.

For targeted audits, scope the audit accordingly (e.g., "Audit only `.vault/exec/...`").

### Review the Audit Report

Scaffold the audit report with `vaultspec-core vault add audit --feature docs-curation`,
then persist the curator's findings into its body. The CLI owns the filename
(`.vault/audit/yyyy-mm-dd-docs-curation-audit.md`) and the frontmatter; never hand-write
either.

Review the report for:

- **Auto-fixed** items (renames, link corrections, frontmatter additions applied by
  `vaultspec-core vault check all --fix`).
- **Flagged** items requiring author input (missing template sections, ambiguous file
  placement).

### Act on Flagged Items

Items the curator cannot auto-fix are listed under **Recommendations**. Orchestrate
these per the delegate model: dispatch the appropriate agent persona (e.g.,
`vaultspec-low-executor` for adding missing sections), or surface items needing author
judgment to the user.

## Artifact Linking

- Any persisted markdown files must be linked against other persisted documents using
  quoted `'[[wiki-links]]'`.

- DO NOT use `@ref` style links or `[label](path)` style links.

### Frontmatter & Tagging Mandate

The curator validates every document against this schema. The `vaultspec-core vault add`
scaffold produces conforming frontmatter for new documents; violations in existing
documents are repaired via `vaultspec-core vault check all --fix` rather than hand
edits:

- **`tags`**: MUST contain the required tag pair in a YAML list.

  - **Directory Tag**: Exactly one of `#adr`, `#audit`, `#exec`, `#index`, `#plan`,
    `#reference`, or `#research` (based on file location).

  - **Feature Tag**: Exactly one kebab-case `#{feature}` tag.

  - *Syntax:* `tags: ['#doc-type', '#{feature}']` (Must be quoted strings in a list).

- **`related`**: MUST be a YAML list of quoted `'[[wiki-links]]'`.

  - *Constraint:* No relative paths (`../`), no bare strings, no `@ref`.

- **`date`**: MUST use `yyyy-mm-dd` format.

- **No `feature` key**: Use `tags:` exclusively for feature identification.

## Requirements

- **Non-destructive**: The curator never deletes files. It repairs through the CLI fix
  paths (renames, link and frontmatter corrections), delegates semantic repairs to
  loaded personas, and flags what neither path can fix.

- **Traceability**: Every modification is logged in the audit report.

- **Standards-first**: All fixes trace back to rules in
  `.vaultspec/rules/rules/vaultspec.builtin.md` and the canonical templates.
