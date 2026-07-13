---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-13'
step_id: S08
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# retire the undocumented code-review-audit double suffix at line 87 in favor of the canonical audit address with optional narrative infix (D2)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`

## Description

- Replace the `-code-review-audit` double-suffix Location address in the Persistence section of `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md` with the canonical audit address
- Add the optional narrative-infix form as the multi-audit disambiguator
- Run mdformat with the 88-column wrap on the edited file

## Outcome

The persona's Persistence Location now matches the canonical audit address with documented infix, implementing ADR decision D2. Verified by grep: zero `code-review-audit` matches remain under `src/vaultspec_core/builtins/`.

## Notes

None.
