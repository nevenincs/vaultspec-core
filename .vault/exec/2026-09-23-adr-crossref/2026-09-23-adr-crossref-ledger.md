---
tags:
  - '#exec'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:563d6867ff5b630b510fb7471b96d903bc5ebb57cada61c387ea235b4ef36823'
related:
  - "[[2026-09-23-adr-crossref-plan]]"
---

# `adr-crossref` ledger

## Changes

- `S01` `A` `.vault/research/2026-09-23-adr-crossref-research.md`
- `S01` `A` `.vault/adr/2026-09-23-adr-crossref-adr.md`
- `S01` `A` `.vault/plan/2026-09-23-adr-crossref-plan.md`
- `S01` `A` `.vault/index/adr-crossref.index.md`
- `S01` `verify:` `vaultspec-core vault check all --feature adr-crossref` -> `pass`
- `S02` `A` `src/vaultspec_core/vaultcore/related_links.py`
- `S02` `A` `src/vaultspec_core/vaultcore/tests/test_related_links.py`
- `S02` `M` `src/vaultspec_core/vaultcore/resolve.py`
- `S02` `M` `src/vaultspec_core/cli/link_cmd.py`
- `S02` `verify:` `pytest vaultcore/tests/test_related_links.py tests/cli/test_link_cli.py tests/cli/test_modified_stamp_mutators.py vaultcore/tests/test_resolve.py` -> `pass`
- `S03` `A` `src/vaultspec_core/crossref/__init__.py`
- `S03` `A` `src/vaultspec_core/crossref/_corpus.py`
- `S03` `A` `src/vaultspec_core/crossref/_engine.py`
- `S03` `A` `src/vaultspec_core/crossref/_models.py`
- `S03` `A` `src/vaultspec_core/crossref/_prefilter.py`
- `S03` `A` `src/vaultspec_core/crossref/_questions.py`
- `S03` `A` `src/vaultspec_core/crossref/_service.py`
- `S03` `A` `src/vaultspec_core/crossref/_wire.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/__init__.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/test_corpus.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/test_service.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/vault.py`
- `S03` `M` `pyproject.toml`
- `S03` `verify:` `ruff check and basedpyright on src/vaultspec_core/crossref` -> `pass`
- `S04` `A` `src/vaultspec_core/cli/vault_crossref_cmd.py`
- `S04` `A` `src/vaultspec_core/tests/cli/test_vault_crossref_cmd.py`
- `S04` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S04` `M` `docs/CLI.md`
- `S04` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S04` `verify:` `pytest tests/cli/test_vault_crossref_cmd.py dev/guards/test_cli_handbook_drift.py tests/cli/test_cli_reference_drift.py tests/cli/test_cli_reference_generated.py` -> `pass`
- `S04` `M` `src/vaultspec_core/crossref/_wire.py`
- `S04` `M` `src/vaultspec_core/crossref/tests/test_service.py`
- `S04` `verify:` `worst-case 50-source sweep reply under the 10,000-token envelope ceiling` -> `pass`
- `S05` `A` `src/vaultspec_core/mcp_server/tools/crossref.py`
- `S05` `A` `src/vaultspec_core/mcp_server/tests/test_crossref_tool.py`
- `S05` `M` `src/vaultspec_core/mcp_server/app.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tools/__init__.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/conftest.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/test_context_budget.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/test_tool_surface.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/test_stdio_e2e.py`
- `S05` `M` `docs/MCP.md`
- `S05` `M` `docs/CLI.md`
- `S05` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S05` `verify:` `pytest src/vaultspec_core/mcp_server` -> `pass`
- `S06` `M` `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`
- `S06` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`
- `S06` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S06` `M` `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
- `S06` `M` `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`
- `S06` `verify:` `pytest test_cli_reference_drift test_corpus_contracts test_discovery_guidance test_cli_language_contract test_template_annotations` -> `pass`
- `S07` `A` `src/vaultspec_core/crossref/tests/test_live.py`
- `S07` `verify:` `pytest src/vaultspec_core/crossref/tests/test_live.py -m typesafe (three runs)` -> `pass`
- `S08` `M` `.vault/adr/2026-07-09-mcp-tool-schema-adr.md`
- `S08` `M` `.vault/adr/2026-08-01-mcp-read-only-adr.md`
- `S08` `verify:` `vaultspec-core vault check all` -> `pass`
- `S03` `M` `src/vaultspec_core/crossref/_engine.py`
- `S03` `M` `src/vaultspec_core/crossref/_service.py`
- `S03` `M` `src/vaultspec_core/crossref/_corpus.py`
- `S03` `M` `src/vaultspec_core/crossref/_models.py`
- `S03` `M` `src/vaultspec_core/crossref/_questions.py`
- `S03` `M` `src/vaultspec_core/crossref/_wire.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/test_bounds.py`
- `S03` `M` `src/vaultspec_core/crossref/tests/test_service.py`
- `S03` `verify:` `pytest src/vaultspec_core/crossref` -> `pass`
- `S04` `M` `src/vaultspec_core/cli/vault_crossref_cmd.py`
- `S04` `verify:` `pytest test_cli_handbook_drift test_cli_reference_drift test_cli_reference_generated test_vault_crossref_cmd` -> `pass`
- `S05` `M` `src/vaultspec_core/mcp_server/tools/crossref.py`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/test_crossref_tool.py`
- `S09` `verify:` `pytest full default suite (5731)` -> `pass`
- `S09` `verify:` `live crossref on this vault: 37 requests, 4.3 s, within 46 and 60 s` -> `pass`
- `S09` `verify:` `live crossref sweep of 3 cadrumo ADRs (534): 38 requests and 7.7-10.4 s per source, within 46 and 60 s` -> `pass`
- `S03` `M` `src/vaultspec_core/crossref/tests/test_bounds.py`
- `S03` `A` `src/vaultspec_core/crossref/tests/test_sweep_safety.py`
- `S03` `M` `src/vaultspec_core/vaultcore/related_links.py`
- `S04` `M` `src/vaultspec_core/tests/cli/test_vault_crossref_cmd.py`
- `S04` `verify:` `pytest test_vault_crossref_cmd test_cli_handbook_drift test_cli_reference_drift test_cli_reference_generated` -> `pass`
- `S05` `verify:` `pytest test_crossref_tool test_context_budget test_tool_surface` -> `pass`
- `S06` `verify:` `pytest test_corpus_contracts test_cli_language_contract test_discovery_guidance test_template_annotations` -> `pass`
- `S03` `M` `src/vaultspec_core/crossref/tests/test_sweep_safety.py`
- `S05` `verify:` `pytest test_crossref_tool` -> `pass`

## Notes

- `S06` S06: vaultspec-core sync previewed no changes; this repository refreshes its tracked .vaultspec snapshots in a separate framework commit, so only the builtin sources changed.
- `S08` S08: dogfooded vault adr crossref on the new ADR; four declared links confirmed, the one new candidate (2026-05-17-cli-memory-lifecycle-adr, 0.52) read and declined as topic adjacency.
