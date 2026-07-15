---
tags:
  - '#plan'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
tier: L2
related:
  - '[[2026-07-15-provider-mcp-enrollment-adr]]'
  - '[[2026-07-15-provider-mcp-enrollment-research]]'
  - '[[2026-07-15-provider-mcp-enrollment-reference]]'
---

# `provider-mcp-enrollment` plan

Deliver provider-native MCP enrollment for Claude and Codex with project-safe defaults, explicit broader scopes, ownership-safe migration, and one stable companion reconcile API.

## Description

The accepted provider MCP enrollment ADR governs all three phases. Phase P01 replaces the JSON-only deployment assumption with typed targets, external ownership, provider-native renderers, and the package-aware public seam. Phase P02 connects that engine to existing lifecycle and CLI surfaces without authorizing global writes by default. Phase P03 proves migration and recognition through real host CLIs and publishes the operator contract.

## Steps

### Phase `P01` - establish the typed enrollment engine

Define normalized definitions, provider and scope targets, external ownership state, native renderers, and the stable companion reconcile boundary.

- [x] `P01.S01` - Define typed MCP scope, target, ownership, and tool-spec contracts; `src/vaultspec_core/core/enums.py and src/vaultspec_core/core/types.py`.
- [x] `P01.S02` - Implement ownership state and provider-scope target resolution; `src/vaultspec_core/core/mcps.py`.
- [x] `P01.S03` - Implement Claude JSON and Codex TOML reconciliation, status, prune, and uninstall; `src/vaultspec_core/core/mcps.py`.
- [x] `P01.S04` - Export the stable package-aware companion reconcile API; `src/vaultspec_core/core/__init__.py and src/vaultspec_core/core/mcps.py`.

### Phase `P02` - integrate lifecycle and operator controls

Route install, upgrade, sync, status, prune, and uninstall through selected provider-native targets with project-safe defaults.

- [x] `P02.S05` - Wire selected providers and project-default MCP scopes into install, upgrade, sync, and uninstall; `src/vaultspec_core/core/commands.py`.
- [x] `P02.S06` - Add provider-scope MCP controls and provider-native status output; `src/vaultspec_core/cli/spec_cmd.py and src/vaultspec_core/cli/root.py`.

### Phase `P03` - prove native hosts and publish guidance

Verify migrations and real Codex and Claude recognition, then document the provider and scope contract for operators and companion packages.

- [ ] `P03.S07` - Add real-behavior reconciliation, migration, lifecycle, and mode-rendering tests; `tests/test_mcps.py and tests/test_commands.py`.
- [ ] `P03.S08` - Add isolated Codex and Claude CLI acceptance and update MCP operator guidance; `tests/cli/test_mcp_hosts.py and docs/MCP.md`.

## Parallelization

P01 is ordered because its contracts bind both native adapters. P02 follows P01 and its two steps are ordered so the CLI exposes only completed lifecycle semantics. In P03, engine regression tests and isolated host acceptance can be developed independently after P02; documentation follows verified behavior. Formal review and release gates follow all steps.

## Verification

- Focused Ruff, type, and pytest gates pass for every touched module.
- Fresh Claude project install remains visible to `claude mcp get` through `.mcp.json`.
- Fresh trusted Codex project install is visible to `codex mcp get` through `.codex/config.toml`.
- Project dry-run, second sync, prune, provider uninstall, and full uninstall are byte-safe and ownership-safe.
- Explicit local or user scope writes only the selected host scope in isolated homes; no default command writes user configuration.
- Dependency/dev and tool definitions render through the declared package mode, including the optional RAG tool distribution spec.
- Provider-native status reports missing, drifted, stale, and external entries without a false green.
- The complete repository quality gate and formal Vaultspec code review pass before publication.
