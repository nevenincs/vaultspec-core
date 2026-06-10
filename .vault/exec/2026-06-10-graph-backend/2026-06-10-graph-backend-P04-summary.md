---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# `graph-backend` `P04` summary

Phase `P04` added a fingerprint-plus-content-hash graph cache so repeated one-shot reads
stop re-parsing the whole corpus, wired cache invalidation into the mutating verbs, and
added scale benchmarks behind a dedicated marker. The cache is an optimisation over a
correctness-critical path, so its soundness contract (a stale cache is never trusted) is
the centre of the design. The phase passed code review with no critical or high findings,
and a follow-up pass closed all medium and low notes.

- Created: `src/vaultspec_core/graph/cache.py`
- Created: `src/vaultspec_core/cli/_cache_hook.py`
- Created: `src/vaultspec_core/graph/tests/test_cache.py`
- Created: `src/vaultspec_core/graph/tests/test_scale.py`
- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/cli/link_cmd.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/cli/plan_cmd.py`
- Modified: `pyproject.toml`
- Modified: `.gitignore`

## Description

`S28` created the cache module: a manifest mapping each scanned file to its size, mtime,
and SHA-256, plus a JSON node-link store of the built canonical graph. Validation passes
only when the file set and every fingerprint match exactly. JSON was chosen over pickle
for inspectability and to avoid code execution on load.

`S29` wired cache loading into graph construction: a passing validation loads the
serialised graph and skips re-parsing, while any mismatch or any unreadable, malformed,
or schema-mismatched cache degrades silently to a full rebuild and rewrites the cache. A
cache-loaded graph reconstructs an object proven equivalent to a fresh build across
nodes, edges, every edge and node attribute, metrics, and dangling links.

`S30` added a single shared invalidation hook that the mutating verbs call after a
successful, non-dry-run, actually-mutating write.

`S31` added cache correctness tests proving a stale cache is never trusted: a changed,
added, or removed file forces a rebuild; a corrupt cache rebuilds; a cache load matches a
fresh build; and a CLI mutation refreshes the cache. `S32` added 500 and 5000 document
scale benchmarks with generous tripwire thresholds, and `S33` registered the benchmark
marker so the benchmarks are deselected from the default run.

## Outcome

Code review returned PASS with no critical or high findings. The soundness contract holds
through four layers: file-set equality, size and mtime, a content hash closing the
same-tick same-size window, and explicit invalidation from the mutating verbs, with
fail-safe degradation underneath. A follow-up pass closed all six review notes: explicit
invalidation was extended to the remaining vault-mutating verbs (the plan structural
verbs, annotation sanitize, and feature index) through their shared write points; a pure
unit test now isolates the content-hash guard independently of mtime; the warm-versus-cold
benchmark gained slack to avoid CI flakiness; the loaded-graph stem index now excludes
phantoms to match fresh-build semantics; the single-document add invalidation was
documented as correctly gated; and the cache save now swallows any exception so a write
failure can never break a build.

## Notes

The cache lives under the auxiliary `data` directory inside the vault, which the document
scan excludes and the install gitignores, so it is never fingerprinted into its own
manifest, graphed, or linted. The serve daemon and the optional semantic-similarity extra
remain deferred to follow-on features as decided in the ADR.
