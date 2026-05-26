---
name: vaultspec-plan-editing-discipline
---

# Plan editing discipline: structure first, prose last

Second worked example of codification applied to an audit finding. Promoted from the
rolling CLI UX audit (finding B6) following the discipline described in the
`vaultspec-codify` rule.

## Rule

When authoring or revising a plan document, complete every Wave, Phase, and Step
structural mutation through the `vaultspec-core vault plan {wave,phase,step}` CLI verbs
**first**. Author or revise the plan's Description, Parallelization, and Verification
prose sections **last**, after every structural operation has settled.

## Why

The rolling CLI UX audit's B6 finding reproduced three times across two persona agents
and two sandboxes: every invocation of `vaultspec-core vault plan step add` on a plan
containing author-written prose silently rewrites the body and discards the prose
sections. The plan template instructs the author to write the prose; the CLI then
deletes it. The agents who survived this bug were the ones who happened to add Steps
before writing prose — never the other way around.

The sibling ADR `cli-plan-body-preservation` proposes the underlying fix (round-trip
preservation of unknown blocks in the serialiser, plus universal `--dry-run` on the
plan-editing surface) landing in the umbrella plan's `W03.P07`. Until that ships, this
rule is the operator discipline that survives the bug by ordering.

## How

The canonical ordering for new plans:

1. `vaultspec-core vault add plan --feature <tag> --tier <L1..L4> --title ... --related ...`
   to scaffold.
1. `vaultspec-core vault plan epic intent edit --text ...` at L4.
1. `vaultspec-core vault plan wave add --title ... --intent ...` for each Wave, in
   order, at L3+.
1. `vaultspec-core vault plan phase add --wave W## --title ... --intent ...` for each
   Phase, in order, at L2+.
1. `vaultspec-core vault plan step add --phase P## --action ... --scope ...` for each
   Step, in order.
1. **Only now** open the plan and author the Description, Parallelization, and
   Verification prose sections via direct file edit.

The canonical ordering for revising an existing plan:

1. If the plan already contains author prose sections, copy them aside in your working
   memory before invoking any `vaultspec-core vault plan step ...` verb.
1. Run every structural verb (`step add`, `step move`, `step insert`, `step remove`,
   `phase add`, `phase remove`, `wave add`, `tier promote`, etc.) before re-authoring
   prose.
1. Restore or re-author the prose sections last.

Worked examples:

- **Good:** scaffold a fresh plan, `epic intent edit`, `wave add` ×N, `phase add` ×M,
  `step add` ×K, **then** open the file and write Description / Parallelization /
  Verification.

- **Good:** revising a plan whose prose you wrote last week, copy the prose into a
  scratch buffer, run a sequence of `step move` and `step add` invocations, restore the
  prose afterwards.

- **Bad:** scaffold the plan, write the Description prose immediately, then invoke
  `step add`. The Description is gone. No warning was printed; no diff was shown.

- **Bad:** alternate structural and prose edits on the same plan in one session. Every
  structural mutation overwrites every prose mutation since the last structural one.

## Status

Active. Once `cli-plan-body-preservation` `W03.P07` lands (the serialiser preserves
unknown-but-positioned blocks verbatim and every plan-editing verb supports
`--dry-run`), the ordering constraint disappears: prose and structure may interleave
freely because the serialiser stops destroying what it does not own. The rule's body
shortens to a pointer at the new behaviour. The rule's intent (treat the plan as one
cohesive document) survives the fix; only the procedure changes.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B6 sharp (three
reproductions). Sibling decision ADR `2026-05-17-cli-plan-body-preservation-adr`.
Umbrella plan steps `W03.P07.S23`, `S24`, `S25`, `S26` in
`2026-05-17-cli-simplification-ux-plan`.
