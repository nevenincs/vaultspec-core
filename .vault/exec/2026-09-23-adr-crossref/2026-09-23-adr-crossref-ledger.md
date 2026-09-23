---
tags:
  - '#exec'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:e4f72288b1f13fbabfed1c1a1d4387d960ca264a9daa4090be6a23479c4c7c0c'
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
