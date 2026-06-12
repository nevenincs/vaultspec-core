---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S46
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# swap the named drafting persona from vaultspec-writer to vaultspec-adr-researcher, leaving the writer mandate plan-only (D10)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`

## Description

- Replace the Workflow's "Draft ADR using an appropriate agent persona, such as
  `vaultspec-writer`" bullet with the `vaultspec-adr-researcher` persona, which
  formalizes the research-backed decisions into ADR content and returns it for
  persistence into the scaffolded document, noting parenthetically that the
  `vaultspec-writer` mandate is plan-only (D10)
- Run mdformat --wrap 88 on the edited file

## Outcome

The vaultspec-adr skill now names the persona that actually owns ADR drafting per
S45, closing the contract drift where the skill routed ADR authorship to a persona
whose tagging mandate covers `#plan` only. D10 is complete: persona body (S45) and
skill (S46) agree.

## Notes

The bullet's return-for-persistence phrasing keeps the S45 read-only contract and the
P04.S20 scaffold-then-edit-body path consistent in the same skill. The "considere
null and void" typo two bullets above is P08.S79.
