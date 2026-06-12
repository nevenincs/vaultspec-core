---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S52
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the template mandate, the standard frontmatter-and-tagging mandate, and an explicit pointer to the vaultspec-reference-auditor persona (D8)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`

## Description

- Add the template mandate to Required steps, pointing at
  `.vaultspec/rules/templates/reference.md` (the post-S50 filename) with the same
  read-and-use wording the sibling `vaultspec-adr` skill carries
- Replace the anonymous "use appropriate focused agents" bullet with an explicit
  instruction to load the `vaultspec-reference-auditor` agent persona, including the
  post-P05 return-findings-for-persistence contract
- Add the standard Frontmatter & Tagging Mandate section (directory tag `#reference`,
  `#{feature}` feature tag, related/date/no-feature-key constraints) in the post-P04
  scaffold-then-verify framing copied from the reworded sibling skills
- Point the Research & Audit coordination wording at the loaded persona
- Format with mdformat at wrap 88

## Outcome

The `vaultspec-code-research` skill is no longer the only artifact-producing skill
without a frontmatter-and-tagging mandate, and two of the research's orphaned firmware
members are wired in: the reference template now has a consuming skill that names it,
and the `vaultspec-reference-auditor` persona now has a loader. The skill's tag
example uses the `#{feature}` convention placeholder, so the P08 literal-tag sweep
gains no new target.

## Notes

The mandate block mirrors `skills/vaultspec-adr/SKILL.md` post-P04.S20 verbatim except
for the directory tag and the `#{feature}` placeholder syntax example.
