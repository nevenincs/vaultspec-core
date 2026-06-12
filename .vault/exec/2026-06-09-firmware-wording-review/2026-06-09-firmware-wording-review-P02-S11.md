---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S11
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# shorten the rule per its own Status clause now that archive dry-run, the paired unarchive verb, and exit-1 on nonexistent tags have landed, replacing the version anchor with a dated verification note (D5)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`

## Description

- Re-verify the three CLI facts against the live 0.1.26 CLI:
  `vault feature archive --help` lists `--dry-run`; `vault feature unarchive` exists
  ("Restore all archived documents for a feature tag");
  `vault feature archive definitely-nonexistent-tag-xyz --dry-run` prints "Error:
  Feature tag ... matches zero documents" and exits 1
- Shorten the rule per its own Status clause (D5): point the Rule and How sections at
  `archive --dry-run` as the canonical discovery pass, retire the manual discovery
  procedure, the five-gaps claim, and the silent-no-op Bad example
- Replace the version anchor with a dated verification note ("re-verified against the
  live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26") in the Why section
- Rewrite the Status section from anticipatory ("Once ... lands") to landed, naming
  `unarchive` as the reversal verb and the non-zero exit on typo'd tags
- Run mdformat --wrap 88 on the edited file

## Outcome

The archive-discipline rule no longer asserts CLI gaps that 0.1.26 has closed. The
rule's intent (audit incoming references before retirement) survives: the operator
judgment about classifying incoming cross-feature references remains the rule's core,
while the mechanical discovery pass moves to `vault feature archive --dry-run`. The
Source section is unchanged; the stale version pin is replaced by a dated verification
note per decision D5. Body shrank from 81 to 50 lines.

## Notes

The rule body previously contained one em dash (in the retired manual-discovery
section); the rewritten prose contains none, so P08.S93 will find this file already
clean.
