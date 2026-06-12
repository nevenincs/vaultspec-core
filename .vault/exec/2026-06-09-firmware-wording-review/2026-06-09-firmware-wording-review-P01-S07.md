---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-09'
step_id: S07
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# retire the undocumented code-review-audit double suffix at lines 28 and 48 in favor of the canonical audit address with optional narrative infix (D2)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`

## Description

- Replace the three `-code-review-audit` double-suffix addresses in `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md` (issue log, shared agent log, Location mandate) with the canonical audit address
- Add the optional narrative-infix form to the Location mandate as the multi-audit disambiguator
- Run mdformat on the edited file

## Outcome

The skill now persists review findings to the canonical audit address with the documented optional infix, implementing ADR decision D2. Verified by grep: zero `code-review-audit` matches remain in the file.

## Notes

The plan row cites lines 28 and 48; a third occurrence at line 38 (the shared-agent-log instruction) carried the same retired suffix and was updated in the same pass for consistency.
