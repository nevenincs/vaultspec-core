---
tags:
  - '#plan'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:2280a40888c76c8954fb144f896a94b59b9fa05081fe31a0a84d3d882f5e7843'
tier: L2
related:
  - '[[2026-07-27-markdown-feature-scope-adr]]'
  - '[[2026-07-27-markdown-feature-scope-research]]'
---

<!-- RETIRED: S01, S02 -->

# `markdown-feature-scope` plan

## Description

This L2 plan executes the accepted narrow scanner-boundary decision. It preserves lazy migration behavior for every existing caller while isolating feature-scoped Markdown repair, then proves the safety contract through the actual CLI against an installed stale workspace.

## Steps

### Phase `P01` - prove selected repair byte preservation

Establish a real stale-workspace CLI regression before implementation changes the migration boundary.

- [x] `P01.S03` - Add a stale-workspace CLI regression for feature-scoped Markdown repair; `src/vaultspec_core/tests/cli/test_migration_triggers.py`.

### Phase `P02` - isolate feature-scoped markdown repair

Preserve default lazy migration behavior while providing the scoped repair path a non-migrating document scan.

- [x] `P02.S04` - Add an opt-in migration-control parameter that preserves the default scanner contract; `src/vaultspec_core/vaultcore/scanner.py`.
- [x] `P02.S05` - Route feature-scoped Markdown checks through the non-migrating scanner mode; `src/vaultspec_core/vaultcore/checks/markdown.py`.

## Parallelization

Phase P01 must complete before P02 because the CLI regression exercises the new scanner boundary. The steps within P01 are ordered by the scanner API then its Markdown caller.

## Verification

The focused scanner and Markdown tests pass, the real CLI regression proves selected repair can normalize the selected record while the unselected record remains byte-identical, and the completed implementation receives formal code review.
