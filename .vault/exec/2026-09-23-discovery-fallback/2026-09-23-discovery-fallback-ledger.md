---
tags:
  - '#exec'
  - '#discovery-fallback'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:4f22532eff4cae3dea6239a97ef3267b2a48b22819292639f56a8b77b8e4d522'
related:
  - "[[2026-09-23-discovery-fallback-plan]]"
---

# `discovery-fallback` ledger

## Changes

- `S01` `A` `src/vaultspec_core/search/_capability.py`
- `S01` `A` `src/vaultspec_core/search/_filters.py`
- `S01` `M` `src/vaultspec_core/search/__init__.py`
- `S01` `M` `src/vaultspec_core/search/_models.py`
- `S01` `M` `src/vaultspec_core/search/_remediation.py`
- `S01` `M` `src/vaultspec_core/search/_service.py`
- `S01` `M` `src/vaultspec_core/search/_wire.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_remediation.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_service.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/collectors_companion.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S01` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S01` `M` `src/vaultspec_core/cli/vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/cli/status_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/search.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/orientation.py`
- `S01` `M` `src/vaultspec_core/mcp_server/envelope.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_search_tool.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_context_budget.py`
- `S01` `M` `pyproject.toml`
- `S01` `verify:` `just check-python check-type check-size check-complexity check-nesting check-toml framework-reference-check; pytest mcp_server search core tests config dev/guards` -> `pass`
- `S01` `by:` `opus-high`
- `S02` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S02` `M` `src/vaultspec_core/tests/test_discovery_guidance.py`
- `S02` `M` `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
- `S02` `verify:` `just check-python check-type check-markdown check-size check-complexity check-nesting; pytest test_discovery_guidance core/tests cli/test_sync search/test_remediation` -> `pass`
- `S02` `by:` `opus-high`

## Notes

- `S01` MCP status does not carry the companion record: it measured +439 tool-definition chars against a ceiling the envelope ADR forbids raising; the companion reaches agents as the search next step instead
- `S02` Builtins touched only to swap the routing sentence for the new constant; the S04 rewrite owns their prose. SEARCH_ADR removed: no builtin or backend offers the rag ADR search any more
