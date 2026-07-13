---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S58
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the unquoted angle-bracket tier placeholder with a quoted curly-brace placeholder (D14)

## Scope

- `src/vaultspec_core/builtins/templates/plan.md`

## Description

- Replace `tier: <tier>` with `tier: '{tier}'` in the plan template frontmatter,
  retiring the firmware's only angle-bracket placeholder in favor of the quoted
  curly-brace form the frontmatter placeholder table documents
- Add the quoted form `'{tier}'` to the hydration substitution patterns for the tier
  key so scaffolding strips the quotes and writes the unquoted scalar the plan
  frontmatter contract requires (trivial remap permitted by the plan's
  documentation-only constraint)
- Add a unit test covering the quoted-placeholder-to-unquoted-scalar substitution
- Format the template with mdformat at wrap 88

## Outcome

The plan template now carries `tier: '{tier}'`, consistent with the curly-brace
placeholder convention and safe under mdformat (the quoted form is a YAML string, so
mdformat no longer normalizes it to the inline-map form the old workaround guarded).
Hydration substitutes the quoted placeholder first, producing `tier: L1`..`tier: L4`
unquoted, which the emit-time plan frontmatter validator accepts. The legacy `{tier}`,
`<tier>`, and `{tier: null}` patterns remain supported for pre-existing template
copies. Template annotation tests and all hydration tests pass (19 passed).

## Notes

A minimal Python remap accompanied the template edit: `hydration.py` gained the
`'{tier}'` pattern (quotes stripped on substitution) and `test_hydration.py` gained
one covering test. This is the trivial name-mapping update the ADR's constraints
permit.
