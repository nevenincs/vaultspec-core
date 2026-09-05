---
name: vaultspec-code-research
description: Ground a decision or plan in how real code does it. Use when an ADR or plan needs a blueprint from this or another codebase.
---

# Code research (vaultspec-code-research)

Produces a Reference record: how a codebase (this project, a submodule, or an external
reference) implements the thing, as patterns with locators. It is an entry point
alongside `vaultspec-research`; an ADR needs at least one of the two. This skill
terminates within one run.

## Steps

- Locate by meaning: `vaultspec-rag search "<concept and domain nouns>" --type code`,
  and the governing decisions with
  `vaultspec-rag search "<intent>" --type vault --doc-type adr`. Read the epicenter or
  nearest analogue whole, then confirm exact symbols with grep. Where `vaultspec-rag` is
  not installed, the `vaultspec-core` discovery verbs and grep carry the same sequence.
- Scaffold: `vaultspec-core vault add reference --feature {feature}` (or the `create`
  tool). Read `.vaultspec/templates/reference.md`; its hint blocks fix the body shape.
- Audit in this run, or dispatch the `vaultspec-reference-auditor` persona to locate and
  audit the `{feature}` implementation in the named codebase; it returns findings for
  you to persist. If the record exists already, update its body.
- Verify with `vaultspec-core vault check all`.

## Quality gate

- **Faithful.** Exact module and `file:line`; the reference's version or commit pinned.
- **Pattern-level.** Abstractions, boundaries, and module interactions; never pasted
  implementation.
- **Mapped.** How the pattern translates to this codebase, and where it will not fit.
- **Load-bearing only.** The abstractions a re-implementation needs, not a tour.

## Next

If an implementation already exists in this project and the findings alter it, report
that to the user; it is an ADR amendment or a plan change, decided there, never a note
left in the plan body.
