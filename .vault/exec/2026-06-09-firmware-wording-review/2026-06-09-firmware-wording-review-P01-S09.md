---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
step_id: S09
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# confirm the hardcoded audit directory tag stands and the template remains the review-flavored audit body living under .vault/audit/ (D2)

## Scope

- `src/vaultspec_core/builtins/templates/code-review.md`

## Description

- Inspect `src/vaultspec_core/builtins/templates/code-review.md` after the S04-S08 edits landed
- Confirm the frontmatter hardcodes the `#audit` directory tag and the hint block names it as the required directory tag
- Confirm the template body remains the review-flavored audit log (persistent findings appended below the heading)
- Confirm no edit is required: the template carries no retired `-code-review-audit` address and no exec-folder path

## Outcome

Confirmation only; no file edit. With S04 pointing the Verify pipeline cell at the audit directory and S07/S08 retiring the double suffix, the template's hardcoded `#audit` tag now agrees with every surface that references it: documents produced from it live under `.vault/audit/` per the tag taxonomy, exactly as ADR decision D2 prescribes.

## Notes

Confirm-only Step; the commit contains this record and the plan-state change only.
