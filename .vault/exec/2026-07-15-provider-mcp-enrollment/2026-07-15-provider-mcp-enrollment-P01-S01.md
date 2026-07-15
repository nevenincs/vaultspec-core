---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S01'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Define typed MCP scope, target, ownership, and tool-spec contracts

## Scope

- `src/vaultspec_core/core/enums.py and src/vaultspec_core/core/types.py`

## Description

- Define project, local, and user MCP scopes as a canonical enum.
- Define JSON and TOML native target formats.
- Add the immutable provider, scope, path, and format target contract.
- Declare MCP capability for Claude, Antigravity, and Codex without claiming unverified Gemini support.

## Outcome

Core now has an additive typed boundary for provider-native MCP target resolution. Ruff and type checks pass. All 32 tests that did not require temporary paths passed, and the three capability contract tests passed with an explicit pytest base directory.

## Notes

The repository Windows temp compatibility shim calls pytest's numbering helper without its new required `register` argument. The affected tests pass unchanged when pytest receives `--basetemp`; this is pre-existing test infrastructure drift, not an S01 product failure.
