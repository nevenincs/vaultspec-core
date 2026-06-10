---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S14
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# shorten the rule per its own Status clause only after the live prose-preservation confirmation passes, replacing the ordering procedure with a pointer at the preserved-prose behavior (D5)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`

## Description

- Confirm the S14 gate: the S13 live confirmation passed (all three sentinel prose
  sentences survived `phase add`, `step add`, and `step check` byte-for-byte, each
  verb reporting "Preserved 2 unknown blocks")
- Shorten the rule per its own Status clause (D5): retire the structure-first,
  prose-last ordering procedure, the new-plan and revising-plan numbered checklists,
  and the prose-is-gone Bad examples
- Rewrite the Rule section to the cohesive-document intent: structure through the CLI
  verbs, prose by direct edit, free interleaving because the serializer preserves
  authored prose blocks verbatim
- Record the two content-safe nuances from S13 in the How section: prose position may
  reflow on write, `--dry-run` previews every plan mutator, and `--canonicalise` is
  the explicit opt-in that strips unknown prose blocks
- Replace the anticipatory Status with the landed state and a dated verification note
  referencing the 2026-06-10 live confirmation against the 0.1.26 CLI
- Run mdformat --wrap 88 on the edited file

## Outcome

The plan-editing discipline rule no longer describes prose destruction as current
behavior. The ordering constraint is retired per the rule's own Status clause; the
rule's intent (treat the plan as one cohesive document; mutate structure only through
the CLI verbs) survives. The dated verification note points at the live confirmation
evidence recorded in the S13 Step Record per decision D5. The Source section is
unchanged. Body shrank from 87 to 56 lines.

## Notes

The retired sections held this file's British spellings (serialiser, behaviour), both
numbered procedural lists, and the em dash; the rewritten prose uses American
spellings, bullets, and spaced hyphens, so P08.S88, S95, and S107 will find this file
already clean. The "Second worked example" ordinal is retained for P08.S104. The
`--canonicalise` flag keeps its CLI-defined spelling since it names a literal flag.
