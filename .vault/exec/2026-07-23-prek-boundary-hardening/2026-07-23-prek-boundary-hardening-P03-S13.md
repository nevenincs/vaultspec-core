---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S13'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add real-filesystem tests for the migration verb: fresh transplant, idempotent re-run as a no-op, --dry-run leaving the tree untouched, dependency-mode and tool-mode entry shapes, and managed-block replacement preserving operator-authored TOML content byte-for-byte

## Scope

- `src/vaultspec_core/tests/cli/test_flow_bugs.py`

## Description

- Add TestPrekMigrationVerb: fresh transplant preserving operator content, byte-for-byte idempotent re-run, dry-run leaving the tree untouched, dependency- vs tool-mode entry shapes, in-place managed-block replacement with surrounding operator content intact, conflicting/missing/unparseable refusals, and a tomllib round-trip of the rendered file recovering the full canonical hook set

## Outcome

Files: `src/vaultspec_core/tests/cli/test_flow_bugs.py`
