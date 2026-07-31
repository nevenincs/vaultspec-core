---
tags:
  - '#adr'
  - '#skill-audit'
date: '2026-02-22'
modified: '2026-06-28'
body_hash: 'sha256:e5276fe27ae5b7b0b913e378cb8d04f649b64da8c02949a81b7ffdb26bc6766b'
related:
  - '[[2026-02-22-skill-audit-research]]'
---

# ADR: Standardize Skill Structure | (**status:** `accepted`)

## Context

The project's skill definitions in `.vaultspec/rules/skills` currently exist as flat Markdown files. This violates the official [Agent Skills specification](https://agentskills.io/specification), which mandates a directory-based structure (`skill-name/SKILL.md`) with specific metadata fields (`name`). This non-compliance prevents the use of standard tooling (`skills-ref`) and inhibits proper "progressive disclosure" mechanisms.

## Decision

We will refactor the `.vaultspec/rules/skills` directory to strictly adhere to the Agent Skills v1.0 specification.

### specific Changes

1. **Directory-based Skills:** Every `vaultspec-*.md` file will be converted to a directory named `vaultspec-*`.
1. **SKILL.md:** The content of the original markdown file will be moved to `SKILL.md` inside the new directory.
1. **Metadata Injection:** The `name` field will be added to the YAML frontmatter of every `SKILL.md`, matching the directory name.

## Consequences

- **Positive:** Full compliance with Agent Skills spec; compatibility with `skills-ref` validation and prompt generation tools; better organization for future skill assets.
- **Negative:** Requires a one-time migration of all skill files.

## Validation

All refactored skills must pass `skills-ref validate`.
