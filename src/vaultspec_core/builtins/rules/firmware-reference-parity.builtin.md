---
name: firmware-reference-parity
---

# Firmware reference parity: named artifacts must resolve

A worked example of codification applied to an audit finding. Promoted from the firmware
wording review audit following the discipline described in the `vaultspec-codify` rule.

## Rule

Every skill, persona, template, or CLI verb named in firmware prose - the bundled rules,
system fragments, skills, personas, and templates under `src/vaultspec_core/builtins/` -
must resolve to a shipped artifact of exactly that name, and a rename must update every
referencing surface in the same change.

## Why

The firmware is consumed by agents at session load, so a dangling name in an always-on
mandate degrades every downstream session. The
`2026-06-10-firmware-wording-review-audit` documented two such breakages: a phantom
`vaultspec-write-plan` skill name routing the Plan phase across the pipeline table,
intent table, and catalog (the shipped directory is `vaultspec-write`), and an orphaned
`ref-audit.md` template left behind by a rename. Both were renames that updated one
surface and left the old name standing in the others, contradicting the firmware's own
consistency mandate.

## How

- Before naming a skill, persona, template, or verb in firmware prose, confirm it ships:
  `vaultspec-core spec <resource> list` (one of `rules`, `skills`, `agents`) enumerates
  the shipped artifacts to check names against, and the template files live under
  `src/vaultspec_core/builtins/templates/`.

- **Good:** renaming a skill updates the pipeline table, the intent table, the catalog,
  and every cross-reference atomically in one change, so no surface names the old slug.

- **Bad:** renaming the skill directory (or template file) and leaving the old name in
  the system prompt, a discipline rule, or another skill's prose; the next agent loads a
  reference to an artifact that no longer exists.

## Status

Active. Until a structured firmware-name linter lands, the cross-surface sweep is the
author's discipline; `vaultspec-core spec <resource> list` is the check.

## Source

Audit `2026-06-10-firmware-wording-review-audit`, findings REVIEW-001 and REVIEW-002 and
the campaign's renamed-artifact root cause. Sibling decision ADR
`2026-06-09-firmware-wording-review-adr` (decisions D1 and D7).
