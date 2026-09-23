---
tags:
  - '#exec'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:04b5d70cbdafc7bd09368836dcc5192ede70085a33edb59b35a1278344f32bb2'
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
