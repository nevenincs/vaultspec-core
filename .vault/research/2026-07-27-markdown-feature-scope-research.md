---
tags:
  - '#research'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-markdown-feature-scope-reference]]"
---

# `markdown-feature-scope` research: `feature-scoped repair migration boundary`

Issue #268 asks whether a feature-scoped markdown repair can preserve a strict
no-unrelated-mutation boundary while the workspace has pending migrations. The
source reference establishes that the checker filter is sound but the scanner
performs a whole-workspace mutation before that filter; the evidence favors a
narrow, opt-in non-migrating scan for this explicit scoped-repair path. The ADR
must settle its compatibility boundary.

## Findings

### Feature filtering is already correct at the markdown-writer boundary

The command forwards `--feature` to `check_markdown`, which normalizes the tag,
excludes nonmatching documents, and only then calls `atomic_write` for a detected
hygiene change. `src/vaultspec_core/cli/vault_cmd.py:1521-1543`;
`src/vaultspec_core/vaultcore/checks/markdown.py:139-212`. Changing the predicate
would add risk without addressing the pre-filter mutation.

### Lazy schema convergence violates a feature-scoped repair boundary

`scan_vault` invokes `run_pending_migrations` before it yields a document path.
The registry can run `modified_stamp_backfill`, which walks all vault Markdown
documents and writes missing `modified:` fields. A selected-feature command can
therefore mutate unrelated documents before it has read their tags.
`src/vaultspec_core/vaultcore/scanner.py:34-55`;
`src/vaultspec_core/migrations/__init__.py:198-295`;
`src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py:54-151`.

### Three boundaries were compared

Retaining unconditional scanner migration preserves the historic lazy-convergence
behavior but fails the issue's byte-preservation requirement. Making every
scanner consumer migration-free would provide the broadest read safety, but it
changes the established `scan_vault` contract used by creation and index commands
without evidence that this issue requires that larger migration redesign.
An optional scanner mode that defaults to current behavior bounds the change:
feature-scoped markdown repair can scan without migrations, while all existing
callers remain convergent unless they explicitly opt out. The compatibility and
safety evidence favors the narrow mode.

### A CLI-level stale-manifest regression is required

The existing markdown feature test only observes warnings in an uninstalled
temporary directory, so no registry can run. The existing migration-trigger suite
uses a real installed workspace, rewinds its manifest, and invokes the actual CLI;
that is the appropriate pattern for a byte-level selected-versus-unselected test.
`src/vaultspec_core/vaultcore/checks/tests/test_markdown.py:129-134`;
`src/vaultspec_core/tests/cli/test_migration_triggers.py:267-308`.

### The reported structural and encoding damage is outside markdown hygiene

The hygiene transform changes trailing whitespace, blank runs, and final newlines
only; it decodes and writes UTF-8. The known migration writes frontmatter stamps,
not plan sections. No audit was able to reproduce the reported repeated headings
or mojibake from these paths alone, so that portion remains uninvestigated and
should not expand this narrowly scoped repair. `src/vaultspec_core/vaultcore/checks/markdown.py:70-137`;
`src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py:94-151`.

## Sources

- `src/vaultspec_core/cli/vault_cmd.py:1521-1543`
- `src/vaultspec_core/vaultcore/checks/markdown.py:70-212`
- `src/vaultspec_core/vaultcore/scanner.py:34-55`
- `src/vaultspec_core/migrations/__init__.py:198-295`
- `src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py:54-151`
- `src/vaultspec_core/vaultcore/checks/tests/test_markdown.py:129-134`
- `src/vaultspec_core/tests/cli/test_migration_triggers.py:267-308`
