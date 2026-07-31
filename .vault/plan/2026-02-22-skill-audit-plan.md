---
tags:
  - '#plan'
  - '#skill-audit'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:4f4797c8e5cc09e79a7b525def0d63abf67b3697e1be79526a2a49a0f0c01dc8'
tier: L2
related:
  - '[[2026-02-22-skill-audit-adr]]'
  - '[[2026-02-22-skill-audit-research]]'
---

# Plan: Refactor Skills to Spec

## Steps

### Phase `P01` - Preparation

Inventory the flat vaultspec-\*.md skill files under .vaultspec/skills and confirm the skills-ref validation tooling is available.

- [x] `P01.S01` - inventory the flat vaultspec-\* skill files under .vaultspec/skills; `.vaultspec/skills`.

### Phase `P02` - Migration

Move each flat skill file into its own `<name>/SKILL.md` directory with an injected name: frontmatter field.

- [x] `P02.S02` - move each flat skill file into a `<name>/SKILL.md` directory with an injected name field; `.vaultspec/skills`.

### Phase `P03` - Validation

Validate every migrated skill directory and confirm no flat skill files remain.

- [x] `P03.S03` - verify no flat skill files remain outside their SKILL.md directories; `.vaultspec/skills`.

### Phase `P04` - Cleanup

Remove temporary files or logs left over from the migration.

- [x] `P04.S04` - remove temporary files or logs left over from the migration; `.vaultspec/skills`.
