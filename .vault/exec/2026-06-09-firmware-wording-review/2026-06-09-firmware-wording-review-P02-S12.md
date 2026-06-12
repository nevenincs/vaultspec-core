---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S12
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# shorten the rule per its own Status clause, dropping the stale 0.1.19 claims, the empty-upgrade-preview example, and the silent-no-op claim, replacing the version anchor with a dated verification note (D5)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`

## Description

- Re-verify the stale claims against the live 0.1.26 CLI using only help and dry-run
  invocations: `install --upgrade --dry-run` prints a populated per-file preview
  ("Upgrade preview 0.1.26 ... 9 updated 40 unchanged"); `vault feature archive` lists
  `--dry-run` and exits 1 with an error on a nonexistent tag (verified in S11);
  `install`, `uninstall`, and `sync` all list `--dry-run` in `--help`
- Shorten the rule per its own Status clause (D5): affirm `--dry-run` as the canonical
  preview path on every destructive verb in the Rule section
- Drop the stale claims: the asymmetric-gating description as current behavior, the
  archive silent-exit-0 Bad example, and the empty-upgrade-preview Bad example
- Replace the `verified against vaultspec-core --version 0.1.19` anchor with a dated
  verification note ("re-verified against the live CLI on 2026-06-10,
  `vaultspec-core --version` 0.1.26") in the Why section
- Collapse the five-step numbered procedure into the Rule sentence and keep the
  escalate-on-empty-preview guidance as a How bullet
- Run mdformat --wrap 88 on the edited file

## Outcome

The dry-run-discipline rule no longer asserts CLI gaps that 0.1.26 has closed. The
rule's intent (preview before apply) survives as the operator's contract: run the verb
with `--dry-run`, read the preview, apply only when it matches intent, and escalate on
an empty preview. The Why section now records the closed gaps with a dated verification
note instead of a version pin per decision D5. The Source section is unchanged. Body
shrank from 84 to 57 lines.

## Notes

The retired five-step numbered procedure was the numbered list P08.S106 targets in this
file; the shortened body has no numbered lists left. The opening "Third worked example"
ordinal is retained for P08.S105 to handle. No mutating command was run without
`--dry-run` during verification.
