---
name: vaultspec-code-research
description: Ground a decision or plan in how real code does it. Use when an ADR or plan needs a blueprint from this or another codebase.
---

# Code research (vaultspec-code-research)

Produces a Reference record: how a codebase (this project, a submodule, or an external
reference) implements the thing, as patterns with locators. It is an entry point
alongside `vaultspec-research`; sufficient Audit evidence can also ground an ADR. This
skill terminates within one run.

## Steps

- Discover per the `vaultspec-discovery` rule: locate code by meaning, read the
  epicenter or nearest analogue whole, confirm exact symbols with grep, and list the
  decisions.
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

Apply the system's decision coverage test to findings that suggest a change. Routine
execution uses existing scope; a new costly commitment routes to `vaultspec-adr`. Report
findings without changing implementation unless that work is authorized.
