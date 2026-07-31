---
tags:
  - '#plan'
  - '#vault-doctor-suite'
date: '2026-02-24'
modified: '2026-07-31'
body_hash: 'sha256:ee419b1c204a6737ca9e80cd43d2738f44b24542fa556572de5c6b4fa078a3eb'
tier: L2
related:
  - '[[2026-02-24-vault-doctor-suite-research]]'
  - '[[2026-02-24-vault-doctor-suite-adr]]'
---

# `vault-doctor-suite` plan

## Steps

### Phase `P01` - Foundation: check registry, models, and CLI scaffold

Establish the check result models, the check registry entry point, and the vault check CLI command group that replaced vault audit.

- [x] `P01.S01` - define the check diagnostic and result models; `src/vaultspec_core/vaultcore/checks/_base.py`.
- [x] `P01.S02` - implement the check registry entry point that runs every checker; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P01.S03` - wire the vault check command group into the CLI in place of vault audit; `src/vaultspec_core/cli/vault_check_cmd.py`.

### Phase `P02` - Structure and links checks

Detect unsupported vault directory structure, broken wikilinks, orphaned documents, and dangling related links.

- [x] `P02.S04` - implement the structure check for unsupported vault directories and stray files; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `P02.S05` - implement broken-wikilink, orphaned-document, and dangling-link checks; `src/vaultspec_core/vaultcore/checks/links.py`.
- [x] `P02.S06` - implement the orphaned-document check; `src/vaultspec_core/vaultcore/checks/orphans.py`.
- [x] `P02.S07` - implement the dangling related-link check; `src/vaultspec_core/vaultcore/checks/dangling.py`.

### Phase `P03` - Chain integrity checks

Detect gaps in the exec to plan to ADR to research authoring chain and enforce ADR/plan grounding.

- [x] `P03.S08` - implement the schema check enforcing ADR-research and plan-ADR grounding links; `src/vaultspec_core/vaultcore/checks/references.py`.
- [x] `P03.S09` - implement the exec-to-plan mapping check; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.

### Phase `P04` - Frontmatter drift checks

Detect and fix frontmatter format drift: CRLF endings, BOM, unquoted dates, duplicate tags, missing related fields, and stale modified stamps.

- [x] `P04.S10` - implement frontmatter drift checks: CRLF endings, BOM, unquoted dates, duplicate tags, and missing related fields; `src/vaultspec_core/vaultcore/checks/frontmatter.py`.
- [x] `P04.S11` - implement markdown hygiene drift checks and fixes; `src/vaultspec_core/vaultcore/checks/markdown.py`.
- [x] `P04.S12` - implement the modified-stamp drift check and reconciliation; `src/vaultspec_core/vaultcore/checks/modified_stamp.py`.

### Phase `P05` - Feature coverage reporting

Report per-feature document-type coverage so gaps in the research to ADR to plan to exec lifecycle are visible.

- [x] `P05.S13` - implement the feature coverage check reporting document-type completeness per feature; `src/vaultspec_core/vaultcore/checks/features.py`.

### Phase `P06` - Integration, pre-commit, MCP, and docs

Wire the full check suite into pre-commit hooks and the MCP check tool, and update reference documentation to describe vault check in place of vault audit.

- [x] `P06.S14` - add the full-suite integration test running every checker against the project vault; `src/vaultspec_core/vaultcore/checks/tests/test_run_all.py`.
- [x] `P06.S15` - wire the vault-fix pre-commit hook running vault check all --fix; `.pre-commit-config.yaml`.
- [x] `P06.S16` - expose the check suite as the check MCP orientation tool; `src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `P06.S17` - update the CLI reference documentation to describe vault check in place of vault audit; `.vaultspec/reference/cli.md`.
