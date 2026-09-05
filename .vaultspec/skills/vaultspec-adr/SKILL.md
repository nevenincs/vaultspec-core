---
name: vaultspec-adr
description: Record and approve a decision that is costly to reverse. Use after a Research or Reference record exists and before any code builds on the decision.
---

# ADR (vaultspec-adr)

Produces an ADR: one decision, approved by the user, cited by the plan that executes it.
Enter it for any decision the vaultspec sizing marks costly to reverse, at any horizon.
Precondition: a Research or Reference record for the feature exists. If none does, stop;
the next run is `vaultspec-research` when options must be weighed on external evidence,
otherwise `vaultspec-code-research`. This skill terminates within one run.

## Steps

- Ground per the `vaultspec-discovery` rule, decisions first: read every ADR that
  already governs this scope in full. One that does routes through Amend or supersede
  below.
- Scaffold:
  `vaultspec-core vault add adr --feature {feature} --related <research-or-reference-stem>`
  (or the `create` tool). Read `.vaultspec/templates/adr.md`; its hint blocks fix the
  body shape and the status convention.
- Draft in this run, or dispatch the `vaultspec-adr-researcher` persona to formalise the
  grounded decision into ADR content and return it for persistence.
- Verify with `vaultspec-core vault check all`.
- Present the draft to the user and stop. **Nothing builds on the ADR before its
  approval reply.** On approval, set the heading status to `accepted`; until then it is
  `proposed`; a declined draft becomes `rejected` and stays on disk as evidence the path
  was evaluated.

## Amend or supersede

One decision, one governing record.

- **Amend (default).** Refinement, concretisation, narrowed scope, a parameter change:
  rewrite the existing record's body in place, with the same user approval a new ADR
  needs. Status stays `accepted`; the `modified:` stamp carries the revision.
- **Supersede (pivot only).** The decision reverses, or its rationale no longer holds:
  scaffold the new ADR and in the same session run
  `vaultspec-core vault adr supersede OLD --by NEW`, so exactly one record is `accepted`
  for the scope. Never edit status lines of the old record by hand.

## Document boundary

The research grounds, the ADR decides. Cite research and reference findings by stem;
never restate their evidence. A fact the grounding lacks is added to the grounding
first, then cited. Decision language found in a grounding document moves here.
