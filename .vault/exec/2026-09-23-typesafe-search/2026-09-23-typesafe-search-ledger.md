---
tags:
  - '#exec'
  - '#typesafe-search'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:a586d8fb27816df65f9c9f47a48842517736527c6dc16c9fca003af73f37e34f'
related:
  - "[[2026-09-23-typesafe-search-plan]]"
---

# `typesafe-search` ledger

## Changes

- `S02` `A` `src/vaultspec_core/search/__init__.py`
- `S02` `A` `src/vaultspec_core/search/_models.py`
- `S02` `A` `src/vaultspec_core/search/_questions.py`
- `S01` `A` `src/vaultspec_core/vaultcore/markdown.py`
- `S01` `A` `src/vaultspec_core/vaultcore/tests/test_markdown.py`
- `S01` `M` `src/vaultspec_core/core/tags.py`
- `S01` `M` `src/vaultspec_core/core/adr.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/markdown.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/placeholders.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/annotations.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/body_sections.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/adr_status.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/documents.py`
- `S01` `M` `src/vaultspec_core/graph/algorithms.py`
- `S01` `M` `src/vaultspec_core/graph/api.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_edit_tool.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_tags.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/tests/test_adr_status.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/tests/test_body_sections.py`
- `S01` `M` `src/vaultspec_core/vaultcore/checks/tests/test_markdown.py`
- `S03` `M` `src/vaultspec_core/config/config.py`
- `S03` `A` `src/vaultspec_core/config/dotenv.py`
- `S03` `M` `src/vaultspec_core/config/__init__.py`
- `S03` `M` `src/vaultspec_core/config/tests/test_config.py`
- `S03` `A` `src/vaultspec_core/config/tests/test_dotenv.py`
- `S03` `A` `src/vaultspec_core/search/_credential.py`
- `S03` `A` `src/vaultspec_core/search/tests/__init__.py`
- `S03` `A` `src/vaultspec_core/search/tests/test_credential.py`
- `S03` `M` `.env.example`
- `S04` `A` `src/vaultspec_core/search/_transport.py`
- `S04` `A` `src/vaultspec_core/search/tests/scripted_provider.py`
- `S04` `A` `src/vaultspec_core/search/tests/test_transport.py`
- `S03` `M` `src/vaultspec_core/search/__init__.py`
- `S10` `M` `src/vaultspec_core/core/adr.py`
- `S10` `M` `src/vaultspec_core/graph/cache.py`
- `S10` `M` `src/vaultspec_core/graph/cache_io.py`
- `S10` `M` `src/vaultspec_core/mcp_server/tools/documents.py`
- `S10` `M` `src/vaultspec_core/plan/checks/heading_level_check.py`
- `S10` `M` `src/vaultspec_core/plan/checks/vocabulary_check.py`
- `S10` `M` `src/vaultspec_core/plan/parser.py`
- `S10` `M` `src/vaultspec_core/plan/row_contract.py`
- `S10` `M` `src/vaultspec_core/tests/plan/test_checks.py`
- `S10` `M` `src/vaultspec_core/tests/plan/test_parser.py`
- `S10` `M` `src/vaultspec_core/vaultcore/checks/annotations.py`
- `S10` `M` `src/vaultspec_core/vaultcore/checks/body_sections.py`
- `S10` `M` `src/vaultspec_core/vaultcore/checks/placeholders.py`
- `S10` `M` `src/vaultspec_core/vaultcore/edit_engine.py`
- `S10` `M` `src/vaultspec_core/vaultcore/exec_fold.py`
- `S10` `M` `src/vaultspec_core/vaultcore/exec_ledger.py`
- `S10` `M` `src/vaultspec_core/vaultcore/hydration.py`
- `S10` `M` `src/vaultspec_core/vaultcore/links.py`
- `S10` `M` `src/vaultspec_core/vaultcore/markdown.py`
- `S10` `M` `src/vaultspec_core/vaultcore/parser.py`
- `S10` `M` `src/vaultspec_core/vaultcore/tests/test_core.py`
- `S10` `M` `src/vaultspec_core/vaultcore/tests/test_exec_fold.py`
- `S10` `M` `src/vaultspec_core/vaultcore/tests/test_exec_ledger.py`
- `S10` `M` `src/vaultspec_core/vaultcore/tests/test_links.py`
- `S10` `M` `src/vaultspec_core/vaultcore/tests/test_markdown.py`
- `S05` `M` `src/vaultspec_core/mcp_server/catalog.py`
- `S05` `M` `src/vaultspec_core/search/__init__.py`
- `S05` `M` `src/vaultspec_core/search/_models.py`
- `S05` `M` `src/vaultspec_core/search/_questions.py`
- `S05` `M` `src/vaultspec_core/search/_transport.py`
- `S05` `M` `src/vaultspec_core/search/tests/scripted_provider.py`
- `S05` `A` `src/vaultspec_core/search/_corpus.py`
- `S05` `A` `src/vaultspec_core/search/_engine.py`
- `S05` `A` `src/vaultspec_core/search/_lexical.py`
- `S05` `A` `src/vaultspec_core/search/_service.py`
- `S05` `A` `src/vaultspec_core/search/tests/test_corpus.py`
- `S05` `A` `src/vaultspec_core/search/tests/test_engine.py`
- `S05` `A` `src/vaultspec_core/search/tests/test_lexical.py`
- `S05` `A` `src/vaultspec_core/search/tests/test_service.py`
