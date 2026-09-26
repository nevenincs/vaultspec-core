---
tags:
  - '#exec'
  - '#env-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:896092bf682ec76e72258f19b57bea54c803936040696ffca2efb166020f87f3'
related:
  - "[[2026-09-26-env-parity-plan]]"
---

# `env-parity` ledger

## Changes

- `S13` `M` `.vault/adr/2026-02-16-environment-variable-adr.md`
- `S13` `M` `.vault/adr/2026-02-19-workspace-path-decoupling-adr.md`
- `S13` `M` `.vault/adr/2026-05-17-cli-spec-edit-safety-adr.md`
- `S13` `M` `.vault/adr/2026-07-13-install-mode-adr.md`
- `S13` `M` `.vault/adr/2026-07-14-install-parity-adr.md`
- `S13` `M` `.vault/adr/2026-09-23-typesafe-search-adr.md`
- `S13` `verify:` `vaultspec-core vault check all` -> `pass`
- `S13` `by:` `orchestrator`
- `S36` `M` `.vault/adr/2026-09-21-typesafe-classifier-adr.md`
- `S36` `M` `.vault/adr/2026-04-04-test-and-paths-adr.md`
- `S36` `M` `.vault/adr/2026-04-12-vaultspec-rag-install-adr.md`
- `S36` `M` `.vault/adr/2026-06-18-mcp-service-client-adr.md`
- `S36` `M` `.vault/adr/2026-07-13-index-drift-hardening-adr.md`
- `S36` `verify:` `vaultspec-core vault check all` -> `pass`
- `S36` `by:` `vaultspec-docs-curator`
- `S01` `A` `src/vaultspec_core/env_values.py`
- `S01` `M` `src/vaultspec_core/__init__.py`
- `S01` `verify:` `just check-python` -> `pass`
- `S01` `verify:` `just check-type` -> `pass`
- `S01` `verify:` `pytest src/vaultspec_core/config/tests src/vaultspec_core/mcp_server/tests/test_tool_surface.py` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `M` `src/vaultspec_core/config/config.py`
- `S02` `M` `src/vaultspec_core/config/__init__.py`
- `S02` `M` `src/vaultspec_core/core/exceptions.py`
- `S02` `M` `src/vaultspec_core/config/tests/test_environment.py`
- `S02` `M` `src/vaultspec_core/config/tests/test_credential.py`
- `S02` `verify:` `just check-python` -> `pass`
- `S02` `verify:` `just check-type` -> `pass`
- `S02` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/mcp_server/tests src/vaultspec_core/triggers/tests` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/vaultspec_core/config/credential.py`
- `S03` `verify:` `just check-python` -> `pass`
- `S03` `verify:` `just check-type` -> `pass`
- `S03` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/search` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `M` `src/vaultspec_core/cli/json_output.py`
- `S04` `M` `src/vaultspec_core/cli/rendering_hints.py`
- `S04` `M` `src/vaultspec_core/cli/_trigger_trust.py`
- `S04` `M` `src/vaultspec_core/mcp_server/watchdog.py`
- `S04` `A` `src/vaultspec_core/mcp_server/kill_switch.py`
- `S04` `M` `src/vaultspec_core/mcp_server/app.py`
- `S04` `M` `src/vaultspec_core/config/config.py`
- `S04` `M` `src/vaultspec_core/console.py`
- `S04` `M` `src/vaultspec_core/vaultcore/checks/_base.py`
- `S04` `M` `src/vaultspec_core/mcp_server/tests/test_watchdog.py`
- `S04` `verify:` `just check-python` -> `pass`
- `S04` `verify:` `just check-type` -> `pass`
- `S04` `verify:` `pytest src/vaultspec_core/crossref src/vaultspec_core/config src/vaultspec_core/mcp_server/tests src/vaultspec_core/tests/cli src/vaultspec_core/vaultcore/tests` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S05` `M` `src/vaultspec_core/config/config.py`
- `S05` `M` `src/vaultspec_core/mcp_server/app.py`
- `S05` `M` `src/vaultspec_core/config/tests/test_config.py`
- `S05` `verify:` `just check-python` -> `pass`
- `S05` `verify:` `just check-type` -> `pass`
- `S05` `verify:` `pytest src/vaultspec_core/config src/vaultspec_core/mcp_server/tests` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `A` `src/vaultspec_core/config/tests/test_resolution.py`
- `S06` `verify:` `just check-python` -> `pass`
- `S06` `verify:` `just check-type` -> `pass`
- `S06` `verify:` `just test-unit` -> `pass`
- `S06` `by:` `vaultspec-high-executor`
- `S40` `by:` `orchestrator`
- `S43` `M` `src/vaultspec_a2a/providers/_harness_mcp_registry.py`
- `S43` `M` `src/vaultspec_a2a/providers/tests/test_acp_mcp.py`
- `S43` `verify:` `pytest src/vaultspec_a2a/providers/tests/test_acp_mcp.py` -> `pass`
- `S43` `verify:` `ruff check` -> `pass`
- `S43` `by:` `vaultspec-low-executor`

## Notes

- `S36` Paths are in the vaultspec-rag repository, commit aeddb984 on its feat/env-parity branch.
- `S40` The user approved the decision, the plan and the a2a operating-model change together in session on 2026-09-26; no file changed.
- `S43` Paths are in the vaultspec-a2a repository, commit 368b64f6 on its feat/env-parity branch.
