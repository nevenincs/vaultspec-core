---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S30
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# invalidate or refresh the graph cache from every mutating verb that touches vault documents

## Scope

- `src/vaultspec_core/cli/`

## Description

- Added a single shared cache-invalidation hook that drops the graph cache file for a
  vault root and never raises, so a failed invalidation can never break the mutating
  verb that triggered it.
- Called the hook from the link add and link remove verbs after a successful,
  state-changing write.
- Called the hook from the feature archive and unarchive verbs when a non-dry-run run
  actually moved documents.
- Called the hook from the add verb on both the all-steps scaffolding path and the
  single-document path when a non-dry-run write occurred.
- Called the hook from the check-all verb when a fix run applied at least one fix, and
  from the repair verb when a non-dry-run run reported changed files.

## Outcome

Every CLI surface that mutates vault documents now drops the graph cache after a
successful write, so the next graph build rebuilds from the corpus rather than trusting
a manifest alone. The hook is one function reused across six call sites rather than
logic scattered per verb. Lint, format, and type checks pass; the 37 link and vault CLI
tests pass unchanged.

## Notes

Invalidation is gated on an actual mutation, not merely on entry: each call site checks
that the run was not a dry-run and that something genuinely changed (an edge added or
removed, documents archived, fixes applied, or files changed by repair), so a no-op
verb does not needlessly discard a warm cache. Dropping the cache file rather than
rewriting it is deliberate: a delete is cheap and idempotent, and the next build
rebuilds and re-caches, so the explicit invalidation reinforces the fingerprint guard
without the verb needing to know how to serialise a graph.
