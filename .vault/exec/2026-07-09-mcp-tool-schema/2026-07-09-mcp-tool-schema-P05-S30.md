---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S30'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
  - "[[2026-07-09-mcp-tool-schema-audit]]"
---

# Review the full nine-tool surface for ADR and reference fidelity: owning-verb routing, isError and envelope contract, annotations, and the subprocess injection guard (agent: vaultspec-code-reviewer)

## Scope

- `src/vaultspec_core/mcp_server`

## Description

- Ran the mandatory `vaultspec-code-reviewer` audit over the full nine-tool surface (diff `0a1a102..HEAD`) against the ADR and reconciliation reference.
- Verified the `invoke` subprocess boundary (argv-list, no shell, catalog and denylist validation before spawn, positional arity checks), the batch and blob-hash reconciliation contract, `isError` and annotation fidelity, owning-verb routing, extraction fidelity, and test integrity.
- Applied the review outcomes: one medium latent isolation fix plus three low hardening fixes, each with a regression test.

## Outcome

Verdict PASS - no critical or high findings. The medium latent context-isolation defect (async handler bodies were not run inside the copied context) and three low items (dash-leading positional hardening, silent double-dot stripping in tag normalization, and the global `find` limit semantics) were all resolved with real regression tests. The canonical gate `pytest src/vaultspec_core -m unit` remains green at 1591; the MCP suite passes. Findings and resolutions are recorded in the linked audit.

## Notes

- No mocks, stubs, or skips introduced. The isolation fix was verified non-tautologically by confirming the new non-leakage test fails against the prior hollow implementation.
