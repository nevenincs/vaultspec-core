---
tags:
  - '#research'
  - '#diagnosis-surface-parity'
date: '2026-06-28'
modified: '2026-06-28'
related: []
---

# `diagnosis-surface-parity` research: `mapping the install/sync/doctor parity surfaces`

A RAG-led, rg-confirmed sweep of every surface that decides whether a provider artifact
matches its source, undertaken to root-cause an observed contradiction between `spec doctor` and `sync`. The question driving it: how many independent bodies of code answer
"is this provider file in sync with its source", and where do they disagree.

## Findings

### One canonical comparator, three divergent readers

The add/update/unchanged decision has a single documented home: `apply_file_sync` in
`src/vaultspec_core/core/sync.py`, which compares the full rendered content byte-for-byte.
Two further surfaces compare content correctly through their own readers - `check_outdated`
in `builtins/__init__.py` and `list_modified_builtins` in `core/revert.py` - but the
doctor's `collect_content_integrity` in `core/diagnosis/collectors.py` was the outlier:
it compared filenames only and never read content. That is the direct cause of the
`spec doctor` says CLEAN / `sync` says UPDATE contradiction on `vaultspec-rag.builtin.md`.

### The intended design already existed

The ambiguous-states resolver ADR specified that content integrity reuse the sync
infrastructure and SHA-256 compare expected transformed output against the actual
destination, and the `ContentSignal` enum already carries a `DIVERGED` value for "file
differs from expected content". The shipped collector never emitted `DIVERGED`, so the
state was dead and content drift was structurally invisible. The fix is a restoration of
the ADR, not a new design: route the doctor through `apply_file_sync` in dry-run.

### The same pattern recurs

The sweep surfaced sibling instances of one root pattern - the same decision made by
divergent code: orphan snapshots that no surface prunes (so `builtin_version` reports
`DELETED` forever); a provider-file registry split between the MCP writer (`core/mcps.py`)
and the doctor's foreign-file detector; an `install --dry-run` preview rendered at
directory granularity while `sync --dry-run` renders per file; and the add/update decision
re-implemented inline by codex agent sync and MCP sync. Each is detailed in the sibling
audit; the codebase-wide hunt for the remainder is tracked in the sweep plan.
