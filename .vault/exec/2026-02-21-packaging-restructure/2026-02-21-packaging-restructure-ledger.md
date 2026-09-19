---
tags:
  - '#exec'
  - '#packaging-restructure'
date: '2026-02-21'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:248de23edeec92cb311a81ee96a7be5b735c7a30d1a50eed2b533f6eee102572'
related:
  - "[[2026-02-21-packaging-restructure-plan]]"
---

# `packaging-restructure` ledger

## Changes

- `S01` `M` `src/vaultspec/core/tests/test_workspace.py`
- `S01` `M` `src/vaultspec/core/tests/test_config.py`
- `S01` `M` `src/vaultspec/vaultcore/parser.py`
- `S01` `M` `src/vaultspec/vaultcore/scanner.py`
- `S01` `M` `src/vaultspec/vaultcore/hydration.py`
- `S01` `M` `src/vaultspec/vaultcore/tests/test_core.py`
- `S01` `M` `src/vaultspec/vaultcore/tests/test_links.py`
- `S01` `M` `src/vaultspec/vaultcore/tests/test_scanner.py`
- `S01` `M` `src/vaultspec/vaultcore/tests/test_types.py`
- `S01` `M` `src/vaultspec/vaultcore/tests/test_hydration.py`
- `S01` `by:` `low-executor`
- `S02` `M` `src/vaultspec/orchestration/session_logger.py`
- `S02` `M` `src/vaultspec/orchestration/subagent.py`
- `S02` `M` `src/vaultspec/orchestration/tests/test_utils.py`
- `S02` `M` `src/vaultspec/orchestration/tests/test_team.py`
- `S02` `M` `src/vaultspec/orchestration/tests/test_load_agent.py`
- `S02` `M` `src/vaultspec/orchestration/tests/test_session_logger.py`
- `S02` `M` `src/vaultspec/orchestration/tests/test_task_engine.py`
- `S02` `M` `src/vaultspec/protocol/acp/claude_bridge.py`
- `S02` `M` `src/vaultspec/protocol/a2a/executors/base.py`
- `S02` `M` `src/vaultspec/protocol/a2a/executors/gemini_executor.py`
- `S02` `M` `src/vaultspec/protocol/a2a/executors/claude_executor.py`
- `S02` `M` `src/vaultspec/protocol/tests/test_sandbox.py`
- `S02` `M` `src/vaultspec/protocol/tests/test_providers.py`
- `S02` `M` `src/vaultspec/protocol/tests/test_permissions.py`
- `S02` `M` `src/vaultspec/protocol/tests/test_fileio.py`
- `S02` `M` `src/vaultspec/protocol/tests/conftest.py`
- `S02` `M` `src/vaultspec/protocol/tests/test_client.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/conftest.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_bridge_lifecycle.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_bridge_sandbox.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_client_terminal.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_bridge_resilience.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_e2e_bridge.py`
- `S02` `M` `src/vaultspec/protocol/acp/tests/test_bridge_streaming.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_discovery.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_french_novel_relay.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_claude_executor.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_e2e_a2a.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_unit_a2a.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_gemini_executor.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_agent_card.py`
- `S02` `M` `src/vaultspec/protocol/a2a/tests/test_integration_a2a.py`
- `S02` `M` `src/vaultspec/hooks/engine.py`
- `S02` `M` `src/vaultspec/hooks/tests/test_hooks.py`
- `S02` `by:` `low-executor`
- `S03` `M` `tests/constants.py`
- `S03` `M` `conftest.py`
- `S03` `M` `tests/conftest.py`
- `S03` `M` `tests/cli/test_team_cli.py`
- `S03` `M` `tests/cli/test_vault_cli.py`
- `S03` `M` `tests/test_config.py`
- `S03` `M` `tests/test_logging_config.py`
- `S03` `M` `tests/benchmarks/bench_rag.py`
- `S03` `M` `src/vaultspec/orchestration/tests/test_session_logger.py`
- `S03` `M` `src/vaultspec/orchestration/tests/test_team.py`
- `S03` `M` `src/vaultspec/protocol/tests/test_providers.py`
- `S03` `M` `src/vaultspec/protocol/acp/tests/test_e2e_bridge.py`
- `S03` `M` `src/vaultspec/protocol/acp/tests/test_bridge_lifecycle.py`
- `S03` `M` `src/vaultspec/protocol/a2a/tests/test_e2e_a2a.py`
- `S03` `M` `src/vaultspec/protocol/a2a/tests/test_french_novel_relay.py`
- `S03` `M` `src/vaultspec/subagent_server/tests/test_mcp_tools.py`
- `S03` `M` `src/vaultspec/rag/tests/test_indexer_unit.py`
- `S03` `by:` `low-executor`
- `S04` `M` `pyproject.toml`
- `S04` `verify:` `uv run vaultspec --help` -> `pass`
- `S04` `by:` `low-executor`
- `S05` `A` `src/vaultspec/server.py`
- `S05` `M` `src/vaultspec/subagent_server/server.py`
- `S05` `A` `src/vaultspec/mcp_tools/__init__.py`
- `S05` `A` `src/vaultspec/mcp_tools/vault_tools.py`
- `S05` `A` `src/vaultspec/mcp_tools/team_tools.py`
- `S05` `A` `src/vaultspec/mcp_tools/framework_tools.py`
- `S05` `M` `tests/subagent/test_mcp_protocol.py`
- `S05` `M` `tests/e2e/test_mcp_e2e.py`
- `S05` `M` `extension.toml`
- `S05` `M` `src/vaultspec/orchestration/subagent.py`
- `S05` `M` `.claude/rules/vaultspec-subagents.builtin.md`
- `S05` `M` `.agent/rules/vaultspec-subagents.builtin.md`
- `S05` `M` `.vaultspec/rules/rules/vaultspec-subagents.builtin.md`
- `S05` `M` `.vaultspec/docs/concepts.md`
- `S05` `M` `.vaultspec/docs/cli-reference.md`
- `S05` `verify:` `pytest` -> `pass`
- `S05` `by:` `low-executor`

## Notes

- `S01` Rows backfilled from the feature's historical execution records; this plan and ledger were reconstructed after execution, not logged contemporaneously.
