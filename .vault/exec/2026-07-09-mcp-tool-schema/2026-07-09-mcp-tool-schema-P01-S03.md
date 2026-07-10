---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S03'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add a single kebab-case feature-and-tag normalizer to vaultcore that strips a leading hash, lowercases, rejects path-traversal, and validates the canonical pattern, returning a typed result (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/vaultcore/normalize.py`

## Description

- Add the `vaultcore.normalize` module owning the single kebab-case feature and tag rule.
- Implement `normalize_feature_tag` to strip a leading hash, trim, lowercase, fold path-separators and drop parent-directory tokens, then validate the canonical kebab-case pattern.
- Return a typed frozen `NormalizeResult` carrying ok, the normalized hash-free value, and a label-scoped error message, printing and raising nothing.
- Expose the shared kebab-case pattern as a module constant so both the CLI and the MCP surface reference one definition.

## Outcome

- `vaultcore.normalize.normalize_feature_tag` is available as the one validator; type check and lint clean.

## Notes

- The normalizer folds path-traversal and lowercases, matching the more lenient MCP behavior; a mixed-case handle is now normalized rather than rejected, which is strictly a superset of the prior CLI acceptance.
