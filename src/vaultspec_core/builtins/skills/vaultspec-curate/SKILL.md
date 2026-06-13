---
name: vaultspec-curate
description: 'Audit and repair the .vault/ vault: frontmatter, wiki-links, naming, templates, structure. Use to clean the vault or fix schema violations.'
---

# Documentation curation skill (vaultspec-curate)

This skill governs the autonomous auditing and maintenance of the `.vault/`
documentation vault. It ensures every artifact conforms to the project's documentation
standards as defined in `.vaultspec/rules/rules/vaultspec.builtin.md`.

**Announce at start:** "I'm using the `vaultspec-curate` skill to audit and clean the
documentation vault."

## When to use

- After completing a feature (post `vaultspec-execute`) to verify documentation trail
  integrity.

- Periodically as vault hygiene maintenance.

- When broken links, missing frontmatter, or organizational drift is suspected.

- Before onboarding a new feature to ensure the vault baseline is clean.

## Workflow

### Dispatch the curator

Load the `vaultspec-docs-curator` agent persona. Instruct it to "Perform a full vault
audit of `.vault/`. Validate frontmatter, wiki-links, naming conventions, template
compliance, and directory structure. Repair violations through
`vaultspec-core vault check all --fix` and the CLI repair paths rather than hand edits,
and produce an audit report."

The curator's operating mode is **Audit -> Delegate -> Verify**: it identifies
violations with precision and orchestrates fixes through the CLI fix paths and loaded
agent personas rather than editing documents in-place itself, then re-scans after every
delegated repair. The one document the curator authors directly is its own audit report.

For targeted audits, scope the audit accordingly (e.g., "Audit only `.vault/exec/...`").

### Review the audit report

The curator scaffolds its report with
`vaultspec-core vault add audit --feature docs-curation` and authors the findings into
the scaffolded body itself. The CLI owns the filename
(`.vault/audit/yyyy-mm-dd-docs-curation-audit.md`) and the frontmatter; never hand-write
either.

Review the report for:

- **Auto-fixed** items (renames, link corrections, frontmatter additions applied by
  `vaultspec-core vault check all --fix`).
- **Flagged** items requiring author input (missing template sections, ambiguous file
  placement).

### Act on flagged items

Items the curator cannot auto-fix are listed under **Recommendations**. Orchestrate
these per the delegate model: dispatch the appropriate agent persona (e.g.,
`vaultspec-low-executor` for adding missing sections), or surface items needing author
judgment to the user.

## Artifact linking

- Any persisted markdown files must be linked against other persisted documents using
  quoted `'[[wiki-links]]'`.

- DO NOT use `@ref` style links or `[label](path)` style links.

## Standards

The curator validates every document against the frontmatter schema defined in the
`vaultspec` rule (`.vaultspec/rules/rules/vaultspec.builtin.md`): the required tag pair,
quoted wiki-links in `related:`, `yyyy-mm-dd` dates, and no `feature` key. The
`vaultspec-core vault add` scaffold produces conforming frontmatter for new documents;
violations in existing documents are repaired via `vaultspec-core vault check all --fix`
rather than hand edits.

## Requirements

- **Non-destructive**: The curator never deletes files. It repairs through the CLI fix
  paths (renames, link and frontmatter corrections), delegates semantic repairs to
  loaded personas, and flags what neither path can fix.

- **Traceability**: Every modification is logged in the audit report.

- **Standards-first**: All fixes trace back to rules in
  `.vaultspec/rules/rules/vaultspec.builtin.md` and the canonical templates.
