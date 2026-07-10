---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S04'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Re-point cmd_add feature and tag validation at the new normalizer, deleting the inline regex copy so the CLI and the MCP surface share one validator (agent: vaultspec-low-executor)

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Import `normalize_feature_tag` into the add verb and drop the now-unused inline `re` import.
- Replace the inline feature-tag regex validation with a call to the shared normalizer, surfacing its error and narrowing the value for the type checker.
- Replace the per-tag inline regex loop with the same normalizer under a tag-scoped label, re-applying the hash prefix to the stored tag.

## Outcome

- The add verb and the MCP surface now share one kebab-case validator; the inline regex copies are gone; type check and lint clean and the add and hydration tests stay green.

## Notes

- The MCP create re-point is deferred to P02 as planned; only the normalizer is published and consumed by the add verb here.
