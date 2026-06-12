---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S19
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# mutator stamp-refresh integration tests exercising the real CLI verbs

## Scope

- `src/vaultspec_core/tests/cli/test_modified_stamp_mutators.py`

## Description

- Add an integration test module that drives the real Typer app through `CliRunner` against documents on the real filesystem, following the established cli test conventions (real files, no mocks or patches, root `-t` target wiring).
- Cover plan step check refreshing a plan's stale stamp to today, while asserting the step really closed.
- Cover a stamp-less plan gaining the field after `date:` on its first mutation, asserting both the value and the schema position.
- Cover adr supersede refreshing both the superseded and the superseding ADR, while asserting the supersedes edge and status flip actually landed.
- Cover link add refreshing the source document it rewrites, while asserting the edge was genuinely added.
- Cover dry-run leaving files byte-for-byte untouched for both plan check and adr supersede, and assert the plan dry-run diff still previews the stamp change so the preview stays truthful.

## Outcome

Six integration tests pass against the real CLI. Expected stamps are derived from `datetime.date.today()` at run time rather than hardcoded, and seeded documents carry a deliberately stale `2020-01-01` stamp (distinct from their `2024-03-04` creation date) so a refresh is an observable, non-tautological change. The stem-resolving verbs run against a real installed workspace via `WorkspaceFactory(...).install()`; plan mutators take a positional path and need only the root target callback. Ruff and ty clean.

## Notes

Plan-mutator verbs expose no per-command `--target` option, so the shared `_run` helper wires the target only through the root-level `-t` flag; appending `--target` to a plan command fails argument parsing. The adr and link verbs resolve their stem arguments against the workspace graph, which requires `.vaultspec/` to exist, hence the install step in those tests.
