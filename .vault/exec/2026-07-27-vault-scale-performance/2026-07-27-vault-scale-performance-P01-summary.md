---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:395b0964d23efa2dd034e775199b2c4ddf787e6333a055882cae50829c45dbe0'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# `vault-scale-performance` `P01` summary

All five Steps closed. The graph and cache layer now follows the accepted
performance architecture: warm cache validation is stat-first with a
racily-clean hash window and a deep-verification escape, descriptive counts
are a separate always-cheap surface no render path can escalate past, and
the remaining cold-build and duplicate-build call sites read warm.

- Modified: `src/vaultspec_core/graph/cache.py`
- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/graph/__init__.py`
- Modified: `src/vaultspec_core/graph/tests/test_cache.py`
- Created: `src/vaultspec_core/graph/tests/test_counts.py`
- Modified: `src/vaultspec_core/mcp_server/tools/documents.py`
- Modified: `src/vaultspec_core/vaultcore/orientation.py`
- Modified: `src/vaultspec_core/vaultcore/query.py`

## Description

Warm reads stopped paying for their own validation: full manifest hashing
moved to the save path and validation trusts size plus mtime except inside
the cache-write tick, with the accepted staleness window pinned by test.
The metrics conflation that made a three-number title cost an all-pairs
centrality pass is split into a cheap counts surface consumed by render
paths and an opt-in analysis surface, enforced by a profiler-backed test.
The MCP create path, the status stats path, and type-filtered listings
each dropped a redundant cold build or full-corpus parse. The full graph
suite (143 tests) and the CLI status and listing families pass.
