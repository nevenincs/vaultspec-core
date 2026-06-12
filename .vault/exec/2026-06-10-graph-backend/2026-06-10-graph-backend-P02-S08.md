---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S08
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# preserve wiki-link and related-link multiplicity by returning per-target counts from the extractors

## Scope

- `src/vaultspec_core/vaultcore/links.py`

## Description

- Change `extract_wiki_links` to return a `collections.Counter` keyed by
  link target, incrementing the count once per occurrence so a body citing
  the same target three times yields a count of three.
- Change `extract_related_links` to return a `collections.Counter` keyed by
  resolved target, preserving duplicate `related` entries as repeat counts.
- Update both docstrings to document the new return type, the multiplicity
  semantics, and the dict-subclass behaviour (iteration yields keys, `in`
  behaves like a set, indexing recovers the count) with Sphinx cross-refs.
- Rewrite the link tests to assert exact `Counter` equality including
  multiplicity (single, duplicate, triple, mixed, aliased-duplicate) and to
  verify the returned object is a `Counter` and that membership/iteration
  still behave like the prior set contract.

## Outcome

Both extractors now retain per-target multiplicity at the source instead of
collapsing to a set. The downstream graph build is unaffected at this step
because the canonical-graph call site iterates keys and tests membership,
both of which a `Counter` supports identically to a set; the retained counts
become available for the explicit-edge weighting in a later step. The 19 link
tests pass, and ruff plus ty report clean on the changed module.

## Notes

The graph build call site uses `links.update(extract_related_links(...))`.
With `Counter`, `update` sums counts rather than unioning a set, which is the
exact body-plus-related multiplicity the weighting step consumes, so no
behavioural regression is introduced by leaving that call site for the
dedicated call-site audit step.
