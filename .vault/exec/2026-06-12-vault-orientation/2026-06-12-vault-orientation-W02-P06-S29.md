---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S29
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add cli tests for vault status covering both modes, hints, json schema, and stem-only output

## Scope

- `src/vaultspec_core/tests/cli/test_vault_status.py`

## Description

- Add `src/vaultspec_core/tests/cli/test_vault_status.py` driving the real Typer app through `CliRunner` against genuine on-disk vault documents, with no mocks, patches, stubs, or skips.
- Build a one-feature vault fixture (research, adr, a plan with two closed steps, one open step, and an unlinked exec record) with distinct stale `modified:` stamps so recency facts are observable.
- Cover the rollup: it lists the in-flight plan with open/closed counts, renders stems only with no absolute paths, `.md`, `exec/`, or backslash tokens, and narrows the recent set under `--limit` and `--since`.
- Cover the trace: a checked step maps to its execution-record stem, an open step renders `no record`, the unlinked record is reported, grounding documents group by type, an unknown target exits 1 naming near-matches.
- Cover hints: the "Suggested Next Step" block appears in human output for both modes and is suppressed by `--no-hints`.
- Cover `--json`: the envelope schema id is `vaultspec.vault.status.v1`, status is `unchanged`, the dataclass-shaped data carries plan counts and step record mappings, and the hints are present under `next_steps`.

## Outcome

The file adds 15 tests, all passing. The full CLI test directory passes with no regressions. Ruff format/check and ty are clean on the test module.

## Notes

The blanket "no slash" assertion was dropped in favour of path-shaped token checks (`.md`, `exec/`, backslash) because the completion fraction `2/3` is a legitimate slash; the stem-only contract is still enforced by asserting the absolute root and `.vault` never appear.
