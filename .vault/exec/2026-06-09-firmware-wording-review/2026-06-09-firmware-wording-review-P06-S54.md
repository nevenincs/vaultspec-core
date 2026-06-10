---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S54
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add vaultspec-team and vaultspec-projectmanager to the supporting-skills table (D8)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Add a "Team coordination / vaultspec-team" row to the supporting-skills table:
  starts coding teams for complex challenges spanning parallel workers
- Add a "Project management / vaultspec-projectmanager" row: coordinates issues,
  milestones, and releases outside the pipeline
- Mimic the existing two-row style (Need / Skill / Purpose, bare skill names, concise
  purpose phrases); Purpose wording derived from each skill's own frontmatter
  description
- Format with mdformat at wrap 88

## Outcome

The two shipped skills the research flagged as appearing in no catalog or intent table
now have supporting-skills rows in the system prompt: `vaultspec-team` as the
parallel-team coordination entry point and `vaultspec-projectmanager` as the
coordination layer that operates outside the pipeline (its own description: never
modifies application code, user-triggered only). The rules-file catalog additions
follow in S55.

## Notes

The intent table was left untouched: both skills are user-triggered or
complexity-triggered rather than intent-phrase-triggered, and the plan row scopes S54
to the supporting-skills table.
