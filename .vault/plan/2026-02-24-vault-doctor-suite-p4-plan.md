---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:7a484467758a38539159c3d5c00716e2953b683e490540d6575433c30590a516'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p1-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P4 plan: Frontmatter Drift Checks

### Phase `P01` - Frontmatter drift checks

Detect and fix frontmatter format drift: CRLF endings, BOM, unquoted dates, duplicate tags, missing related fields, and stale modified stamps.

- [x] `P01.S01` - implement frontmatter drift detection and the batched fix for CRLF, BOM, unquoted dates, duplicate tags, and missing related fields; `src/vaultspec_core/vaultcore/checks/frontmatter.py`.
- [x] `P01.S02` - implement markdown hygiene drift checks and fixes; `src/vaultspec_core/vaultcore/checks/markdown.py`.
- [x] `P01.S03` - implement the modified-stamp drift check and reconciliation fix; `src/vaultspec_core/vaultcore/checks/modified_stamp.py`.
- [x] `P01.S04` - implement the encoding drift check for non-UTF-8 vault documents; `src/vaultspec_core/vaultcore/checks/encoding.py`.
- [x] `P01.S05` - add unit tests for frontmatter, markdown, and modified-stamp drift checks and their fixes; `src/vaultspec_core/vaultcore/checks/tests/test_frontmatter_fields.py`.
