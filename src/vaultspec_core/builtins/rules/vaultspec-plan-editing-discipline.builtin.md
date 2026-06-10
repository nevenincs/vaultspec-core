---
name: vaultspec-plan-editing-discipline
---

# Plan editing discipline: structure first, prose last

A worked example of codification applied to an audit finding. Promoted from the rolling
CLI UX audit (finding B6) following the discipline described in the `vaultspec-codify`
rule.

## Rule

Treat the plan as one cohesive document: route every Wave, Phase, and Step structural
mutation through the `vaultspec-core vault plan {wave,phase,step}` CLI verbs, and author
the Description, Parallelization, and Verification prose sections by direct file edit.
Prose and structure may interleave freely: the serializer preserves authored prose
blocks verbatim across structural mutations.

## Why

The rolling CLI UX audit's B6 finding documented that plan structural verbs once
silently discarded author-written prose sections, forcing a structure-first, prose-last
ordering. The fix proposed in the sibling ADR `cli-plan-body-preservation` has landed:
every structural mutation now reports "Preserved N unknown blocks", and a live
confirmation against a prose-bearing scratch plan (sentinel sentences carried through
`phase add`, `step add`, and `step check`) showed every authored sentence surviving
byte-for-byte (verified against the live CLI on 2026-06-10, `vaultspec-core --version`
0.1.26).

## How

- Prose content is preserved verbatim; prose position may reflow, because the serializer
  re-anchors blocks around the canonical structure on write. Review the diff after a
  structural verb when section ordering matters.
- Every plan mutator accepts `--dry-run` to preview the rewritten document without
  writing it.
- `--canonicalise` is the explicit opt-in that strips unknown prose blocks; never pass
  it on a plan whose prose you mean to keep.

## Status

Active. The serializer fix this rule anticipated (`cli-plan-body-preservation`
`W03.P07`) has landed and was live-confirmed on 2026-06-10: the ordering constraint is
retired, and preservation is the default with stripping behind the `--canonicalise`
opt-in. The rule's intent (treat the plan as one cohesive document; mutate structure
only through the CLI verbs) survives the fix; only the procedure changed.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B6 sharp (three
reproductions). Sibling decision ADR `2026-05-17-cli-plan-body-preservation-adr`.
Umbrella plan steps `W03.P07.S23`, `S24`, `S25`, `S26` in
`2026-05-17-cli-simplification-ux-plan`.
