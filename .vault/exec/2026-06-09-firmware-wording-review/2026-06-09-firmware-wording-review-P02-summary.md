---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P02` summary

Phase P02 (discipline rule refresh) closed all four Steps S11-S14, implementing ADR
decision D5: the three audit-derived discipline rules are shortened per their own
Status clauses now that the 0.1.26 CLI has closed the gaps they guarded, with the
plan-editing shortening gated on a live prose-preservation confirmation that passed.

- Modified: `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`
- Modified: `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`
- Modified:
  `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`
- Created: four Step Records `...-P02-S11.md` through `...-P02-S14.md` in this folder

## Description

S11 (archive discipline): re-verified against the live CLI that `vault feature archive` carries `--dry-run`, that a paired `unarchive` verb exists, and that
archiving a nonexistent tag exits 1 with an error. The rule's body now points at
`archive --dry-run` as the canonical discovery pass, retiring the manual discovery
procedure and the silent-no-op claim; the rule's intent (audit incoming references
before retirement) survives.

S12 (dry-run discipline): re-verified that `install`, `uninstall`, `sync`, archive,
and every plan mutator accept `--dry-run`, and that `install --upgrade --dry-run`
prints a populated per-file preview (9 updated, 40 unchanged against this worktree).
The stale 0.1.19 claims, the empty-upgrade-preview example, and the silent-no-op
example are dropped; `--dry-run` is affirmed as the canonical preview path on every
destructive verb. No mutating command ran without `--dry-run` during verification.

S13 (live preservation confirmation): a scratch L2 plan carrying three sentinel prose
sentences in its Description, Parallelization, and Verification sections survived
`phase add`, `step add`, and `step check` byte-for-byte, each verb reporting
"Preserved 2 unknown blocks". Verdict PASS, clearing the S14 gate. Two content-safe
nuances recorded: prose position may reflow on write, and the scaffolded empty
`related: []` field was dropped on the first structural write. The scratch plan was
deleted afterward, no scratch index was created, and `vault check all` reports all
checks passed.

S14 (plan-editing discipline): the structure-first, prose-last ordering constraint is
retired per the rule's own Status clause. The rule now states that prose and
structure may interleave freely because the serializer preserves authored prose
blocks verbatim, that every plan mutator accepts `--dry-run`, and that
`--canonicalise` is the explicit opt-in that strips unknown prose blocks. The rule's
intent (treat the plan as one cohesive document; mutate structure only through the
CLI verbs) survives.

All three rules replace their `verified against 0.1.19` version anchors with dated
verification notes naming the 2026-06-10 re-verification against `vaultspec-core --version` 0.1.26. Each Step landed as one commit carrying the edit, its Step Record,
and the CLI-driven plan-state change; all pre-commit hooks pass on every commit.
Deviation noted: the S11 commit was amended once during the phase because an
overzealous `mdformat --wrap 88` pass on the plan document wrapped its single-line
Step rows and broke the plan parser; the plan was restored from the prior commit, S11
re-closed via the CLI, and vault documents are formatted with plain `mdformat`
(wrap-88 applies only to builtins and docs) from S12 onward.
