---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S11'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the shared plan resolver: resolve a feature tag or plan stem to a single plan document via vaultcore.query.list_documents, raising a typed ambiguity error when a feature maps to more than one plan (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/plan_resolver.py`

## Description

- Add the shared plan resolver module with a `resolve_plan` function resolving a feature tag or a plan stem/path to a single plan document via the `list_documents` core.
- Apply the same precedence as the orientation trace resolver: an exact plan stem or a path whose stem matches a plan wins first, then a feature owning exactly one plan.
- Raise a typed `PlanResolutionError` carrying the candidate stems when a feature owns more than one plan, or when nothing matches, so ambiguity is a structured error rather than a silent guess.

## Outcome

- A single feature-or-stem resolver that `plan_progress` and `plan_edit` reuse; a feature mapping to several plans is a structured, actionable error.

## Notes

- No blockers.
