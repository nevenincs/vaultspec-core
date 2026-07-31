---
tags:
  - '#reference'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:6befebecf2ba8732cae9c31c6dd37e095fecaed70552f0b13d35bf098ad77a63'
related: []
---

# `markdown-feature-scope` reference: `scoped markdown repair boundary`

Issue #268 was traced through the real CLI dispatch, markdown checker, scanner,
migration registry, and existing integration tests. The finding is a mutation
boundary defect: a feature-scoped repair enters the global migration path before
it can identify the selected feature.

## Summary

`cmd_check_markdown` forwards the `--feature` value directly to
`check_markdown` (`src/vaultspec_core/cli/vault_cmd.py:1521-1543`). The checker
normalizes that feature tag and excludes nonmatching documents before calculating
hygiene or writing bytes (`src/vaultspec_core/vaultcore/checks/markdown.py:139-212`).
The predicate is therefore not the defect.

The checker obtains documents through `scan_vault` (`markdown.py:169`). Before
that scanner yields a path, it unconditionally calls `run_pending_migrations`
(`src/vaultspec_core/vaultcore/scanner.py:34-55`). The migration driver runs all
pending workspace migrations, independent of the command's feature filter
(`src/vaultspec_core/migrations/__init__.py:198-295`). In particular,
`modified_stamp_backfill` walks every `.vault` Markdown file and writes a missing
`modified:` field (`src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py:54-151`).
This is the observed cross-feature mutation.

The smallest compatible boundary is an optional scanner mode that suppresses
lazy migrations. It remains enabled by default, preserving existing command
semantics. A feature-scoped markdown invocation alone opts out, because it has
an explicit no-unrelated-mutation contract. Unscoped markdown repair and command
paths that require schema convergence keep the current default.

The regression must execute the actual CLI using the existing real-workspace
`WorkspaceFactory` pattern in `src/vaultspec_core/tests/cli/test_migration_triggers.py`.
It should install a workspace, write dirty selected and unselected records,
rewind its real manifest to `0.1.28`, run `vault check markdown --fix --feature alpha`, and compare raw bytes. The selected record must receive only markdown
hygiene changes; the unselected record must remain byte-identical and must not
gain `modified:`. The existing markdown test at
`src/vaultspec_core/vaultcore/checks/tests/test_markdown.py:129-134` is read-only
and uses no stale manifest, so it cannot cover this trigger path.

Markdown hygiene itself changes only trailing whitespace, blank runs, and final
newlines (`src/vaultspec_core/vaultcore/checks/markdown.py:70-137`); it neither
adds plan sections nor decodes/re-encodes through a legacy codec. The issue's
reported repeated sections and mojibake require another writer or process, but
the global migration side effect independently violates the feature-scoped safety
contract and is sufficient to reproduce unrelated `modified:` mutations.
