---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:0c6d70a3e23312cc0d8f1307de523ec0b30e97a67ec317853cfaaf53255dc7c4'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-adr]]'
  - '[[2026-02-24-vault-doctor-suite-plan]]'
  - '[[2026-02-24-vault-doctor-suite-p1-plan]]'
  - '[[2026-02-24-vault-doctor-suite-research]]'
---

# `vault-doctor-suite` P2 plan: Structure and Links Checks

## Steps

### Phase `P01` - Structure and links checks

Implement the structure check for vault directory and filename conventions, and the wikilink-format, dangling-link, and orphaned-document checks.

- [x] `P01.S01` - implement the structure check for unsupported directories and filename conventions with fix support; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P01.S02` - implement the wikilink-format check and fix for non-Obsidian-convention links; `src/vaultspec_core/vaultcore/checks/links.py`.
- [x] `P01.S03` - implement the dangling wikilink check for related links resolving to no document; `src/vaultspec_core/vaultcore/checks/dangling.py`.
- [x] `P01.S04` - implement the orphaned-document check for documents with no incoming links; `src/vaultspec_core/vaultcore/checks/orphans.py`.
- [x] `P01.S05` - add unit tests for the structure, links, dangling, and orphans checks; `src/vaultspec_core/vaultcore/checks/tests/test_structure_case_rename.py`.
