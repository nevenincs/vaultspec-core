---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S07'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Add real-behavior reconciliation, migration, lifecycle, and mode-rendering tests

## Scope

- `tests/test_mcps.py`
- `tests/test_commands.py`
- `src/vaultspec_core/tests/cli/test_sync.py`
- `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`

## Description

- Replace shared-file and inline-marker expectations with provider-native targets and external ownership records.
- Exercise Claude and Antigravity JSON plus Codex TOML through real filesystem reconciliation.
- Cover explicit public target enrollment, package-aware tool rendering, independent provider drift, force adoption, prune, migration, dry-run byte stability, and unsupported scope errors.
- Prove selective companion uninstall preserves Core entries and exact Core ownership fingerprints.
- Align fresh-install command and hook assertions with the tool-mode default and include the hooks sync pass in root result labels.

## Outcome

Seventy-one focused command and MCP tests pass, including five new multi-provider native-enrollment cases. Thirty-three broader CLI sync and provider-file tests pass, and twenty-three doctor tests pass. Ruff and Ty pass for every changed test file. The repository-wide collection remains independently blocked by duplicate `test_normalize.py` module names under default import mode; switching to importlib mode exposes an unrelated optional `statistic` package import failure.

## Notes

Tests use real source imports and real files. They do not use mocks, fakes, stubs, monkeypatching, skips, or expected-failure markers.
