---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-13'
step_id: S05
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# document the optional narrative-infix audit filename yyyy-mm-dd-feature-topic-audit.md as the disambiguator for features with multiple audits (D2)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Extend the audit artifact bullet in the workflow-documents list of `src/vaultspec_core/builtins/rules/vaultspec.builtin.md` with the optional narrative infix form for features carrying multiple audits
- Run mdformat on the edited file

## Outcome

The audit artifact definition now documents both the canonical address and the optional disambiguating infix, implementing ADR decision D2 and aligning the convention with existing vault prior art (multi-audit features already use narrative infixes).

## Notes

None.
