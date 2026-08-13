---
tags:
  - '#audit'
  - '#body-hash-integrity'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e7566feb4a3892ba61e4e450e614ffbfa7f8c6e2da9c0856ad22c7e6f5e51bf2'
related: []
---

# `body-hash-integrity` audit: `Body hash integrity review`

## Scope

Review issues 299 and 306 against the canonical plan frontmatter rewrite and generated feature-index ownership boundaries. The review covers CLI, MCP, repair, rename, concurrency, reporting, strict typing, and real-behavior tests.

## Findings

### generated-frontmatter-drift | high | No-op detection preserved corrupted metadata

The initial shortcut compared only the body digest and stored `body_hash`, allowing drift in generator-owned fields to survive. Remediation now requires the complete canonical document, except intentionally preserved timestamps, to match before reporting unchanged.

### creation-date-reset | high | Genuine updates overwrote the creation date

The original generator emitted today into both `date` and `modified`. Remediation preserves a valid existing creation date and advances only `modified` when canonical generated content changes.

### misleading-index-outcomes | medium | No-op indexes were reported as generated

The path-only result prevented CLI and repair callers from distinguishing a write from a no-op. Remediation introduces a typed changed result and projects it through text, JSON, repair planning, cache invalidation, MCP, and rename callers.

### stale-snapshot-overwrite | medium | Concurrent writers could use stale membership

Callers previously collected graph nodes before entering the index write boundary. Remediation serializes each index and refreshes production graph membership under that lock; explicit nodes remain available only for isolated callers and tests.

### swallowed-index-read-error | low | Read failures authorized replacement

The original shortcut swallowed every read `OSError`. Remediation propagates existing-target read failures and leaves the uncertain filesystem object unchanged.

### malformed-frontmatter-crash | medium | Non-mapping YAML could abort regeneration

The generic YAML parser can produce a list or scalar. Remediation treats non-mapping frontmatter as noncanonical and rewrites it instead of calling mapping methods on it.

### duplicate-hash-acceptance | medium | Duplicate hash keys could satisfy a shortcut

Last-key-wins YAML parsing could hide a forged duplicate. Remediation uses complete canonical-text equality for no-op eligibility, so duplicate generator-owned keys force a rewrite to one canonical field.

### owning-path-coverage | medium | Issue 299 lacked CLI and MCP proof

Serializer-only coverage did not prove the reported mutation routes. Remediation adds real CLI and MCP mutations covering nulls, lists, nested mappings and date-like values, with exactly one truthful `body_hash` after persistence.

## Recommendations

- Keep feature-index rendering, membership refresh, locking, timestamp preservation and changed-state reporting in the canonical index module.
- Keep CLI, MCP, repair and rename surfaces as projections of the typed generation result.
- Retain end-to-end CLI and MCP preservation tests alongside serializer-level property coverage.
