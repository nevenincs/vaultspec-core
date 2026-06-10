---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S28
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# create the fingerprint cache module with a size and mtime manifest and a serialised graph store

## Scope

- `src/vaultspec_core/graph/cache.py`

## Description

- Created the graph cache module with pure, isolated load, save, validate, and
  fingerprint functions and no graph-build coupling.
- Defined the fingerprint manifest as a mapping of each scanned vault-relative file
  path to a three-tuple of size, mtime in nanoseconds, and a SHA-256 content hash,
  reusing the size and mtime primitive the repair pipeline already fingerprints with.
- Defined the serialised store as JSON in networkx node-link shape, plus the recorded
  dangling-link pairs, stamped with a versioned cache schema string.
- Implemented validate to return true only when the current file set and every
  per-file fingerprint match the manifest exactly, so any added, removed, or changed
  file is a miss.
- Implemented load to degrade to none on a missing file, malformed JSON, a schema
  mismatch, or a structurally invalid payload, and save to write atomically and
  swallow write failures.

## Outcome

The cache primitive is in place and isolated. The validate decision is the single
point behind stale-never-trusted: it compares the full key set and every fingerprint
tuple. Lint, format, and type checks pass; a smoke check confirmed validate accepts an
identical manifest and rejects both a content-hash change and an added file.

## Notes

Added a per-file SHA-256 content hash to the manifest beyond the bare size and mtime.
The mtime resolution can in principle miss a same-size edit applied within one
timestamp tick, which would let the fast-path guard alone serve stale data; the content
hash closes that window so soundness does not rest on timestamp resolution. The hash is
a single read per file, strictly cheaper than the parse-and-build the cache avoids, so
it is always computed rather than gated. The store is JSON rather than pickle for
inspectability, cross-version safety, and to avoid arbitrary-code execution on load;
the canonical graph carries only JSON-friendly scalar attributes, so JSON round-trips
it without loss. The cache file lives under the auxiliary `data` subdirectory, which is
excluded from the document scan, so it is never itself fingerprinted or treated as a
vault document.
