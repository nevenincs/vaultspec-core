---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S18
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add CLI tests for ego scoping and derived-edge toggles

## Scope

- `src/vaultspec_core/tests/cli/test_vault_cli.py`

## Description

- Add a CLI test class exercising the vault graph JSON envelope through the
  Typer runner against the synthetic project corpus.
- Assert the default JSON carries a separate non-empty `derived_edges` array
  at schema v2, and that `--no-derived` empties it while leaving the canonical
  `edges` array byte-identical.
- Assert `--node` scopes to a strict subset of the full node set containing
  the centre, `--depth 0` returns only the centre, and increasing depth grows
  the neighbourhood monotonically; the centre is discovered from the JSON
  itself rather than hardcoded.
- Assert a missing `--node` exits 1 with a `failed` envelope naming the node,
  and that ego-scoped derived edges keep both endpoints within the scope.

## Outcome

The ego-scoping flags and the derived toggle are covered end-to-end through
the CLI with envelope-shape and exit-code assertions derived from the live
output, not hardcoded stems. The 7 new tests pass; ruff, ruff-format, and ty
are clean.

## Notes

The centre node is selected from the full graph payload by total degree, so
the tests assert relationships (subset, monotonic growth, centre membership)
rather than brittle hardcoded stems, keeping them robust to corpus-generation
changes while still exact about envelope shape and exit codes.
