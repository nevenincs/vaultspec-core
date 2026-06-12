---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S09
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# audit and update every extractor call site for the counted return shape

## Scope

- `src/vaultspec_core/vaultcore/`

## Description

- Grep every extractor call site across `src/`: the only consumers are the
  graph build pass 2 and the `vaultcore` package re-export; the re-export is a
  type-agnostic alias and needs no change.
- Split the graph build pass 2 so body wiki-links and related-frontmatter
  links are extracted into separate Counters rather than merged with a
  set-style `update`, so each resolved edge can later record its provenance.
- Resolve each raw target to its node keys once, summing the source
  multiplicity onto every resolved key and unioning the provenance kind
  (`body`, `related`) into a per-target map; iterate the Counter by key so
  resolution and edge creation behave exactly as before.
- Derive `out_links` from the resolved-target keys so node link sets are
  unchanged while the per-target count and provenance are retained for the
  explicit-edge attribute step.

## Outcome

The single behaviour-bearing call site now consumes the counted return shape
without altering edge topology: all 81 graph tests pass unchanged. The
per-target multiplicity and provenance maps are computed and held in local
scope, ready for the explicit-edge attribute attachment step. ruff and ty
report clean on the graph module.

## Notes

No other call sites exist. The package re-export forwards the symbols
verbatim, so the return-type change propagates to importers without edits.
The combined count is accumulated per resolved node key (after wiki-link
resolution and stem-collision fan-out), not per raw target, so a bare stem
that fans out to several qualified keys contributes its count to each.
