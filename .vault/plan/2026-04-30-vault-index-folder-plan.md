---
tags:
  - '#plan'
  - '#vault-index-folder'
date: '2026-04-30'
modified: '2026-07-31'
body_hash: 'sha256:22ded8464e254257724ae7ed6ca9403fe52a5193918a45e01cceadbcafa3eaee'
tier: L2
related:
  - '[[2026-04-30-vault-index-folder-adr]]'
  - '[[2026-04-30-vault-index-folder-research]]'
---

# `vault-index-folder` plan: dedicated index subfolder migration

## Steps

### Phase `P01` - constants and config

Add the index directory constant and configurable index_dir so later phases have somewhere to target.

- [x] `P01.S01` - add DirName.INDEX and a configurable index_dir with a VAULTSPEC_INDEX_DIR override; `src/vaultspec_core/core/enums.py`.

### Phase `P02` - models, scanner, taxonomy

Recognize the index subdirectory and its #index tag across taxonomy validation and document-type classification.

- [x] `P02.S02` - extend supported directories and tags and validate the index subdirectory in vault structure; `src/vaultspec_core/vaultcore/models.py`.
- [x] `P02.S03` - classify documents under index_dir as DocType.INDEX with a legacy root-level fallback; `src/vaultspec_core/vaultcore/scanner.py`.

### Phase `P03` - generator

Write generated feature indexes into the dedicated index subfolder.

- [x] `P03.S04` - generate feature indexes under docs_dir/index_dir with the #index directory tag; `src/vaultspec_core/vaultcore/index.py`.

### Phase `P04` - structure-checker migration path

Detect legacy root-level indexes and relocate them to the new subfolder.

- [x] `P04.S05` - detect legacy root-level indexes in the structure checker and point operators at the relocation fix; `src/vaultspec_core/vaultcore/checks/structure.py`.

### Phase `P05` - checkers and features integration

Keep the feature-index checker and diagnostics aligned with the new location.

- [x] `P05.S06` - update the feature-index checker fix description to reference the new location; `src/vaultspec_core/vaultcore/checks/features.py`.

### Phase `P06` - CLI, synthetic vault, and template

Update the CLI surface, synthetic corpus pathology, and index template for the new location.

- [x] `P06.S07` - update the feature-index CLI docstring and reference doc for the new location; `src/vaultspec_core/cli/vault_feature_cmd.py`.
- [x] `P06.S08` - relocate the stale-index synthetic-corpus pathology under the index subfolder; `src/vaultspec_core/testing/synthetic.py`.
- [x] `P06.S09` - add the #index directory tag to the index template; `src/vaultspec_core/builtins/templates/index.md`.

### Phase `P07` - documentation and built-in rules

Document the index/ subfolder in project docs and the built-in taxonomy rules.

- [x] `P07.S10` - document index/ in the built-in directory-tag taxonomy and CLI reference; `.claude/rules/vaultspec.builtin.md`.

### Phase `P08` - repo migration and quality gates

Migrate this repo's own vault to the new layout and confirm quality gates pass clean.

- [x] `P08.S11` - migrate this repo's own vault so root-level indexes relocate to .vault/index/; `.vault/index`.
- [ ] `P08.S12` - confirm quality gates pass clean against the migrated vault; `src/vaultspec_core`.
