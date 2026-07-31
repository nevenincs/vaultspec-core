---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:f645e01dc92a3b5c1864a7680758269121b864ce022ce6665a54818e0a9f3d39'
step_id: S110
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# fix the doubled the-dot-vault-vault phrasing in the description (D15)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`

## Description

- Rephrase "for the .vault vault" in the frontmatter description to "for the .vault/
  documentation vault"
- Rephrase the body's "guardian of the `.vault/` vault's integrity" to "guardian of the
  `.vault/` documentation vault's integrity"
- Format the persona with mdformat at wrap 88

## Outcome

The docs-curator persona no longer doubles the word "vault" against the directory name
in either its frontmatter description or its opening body paragraph, per decision D15.
Both spots now use the "`.vault/` documentation vault" noun phrase that the curate
skill adopted in P08.S109, so the skill and its persona describe the artifact store
identically. Verification grep for the doubled phrasing across the file returns zero
matches.

## Notes

None.
