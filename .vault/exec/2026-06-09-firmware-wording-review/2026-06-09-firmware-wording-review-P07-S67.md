---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S67
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add proposed to the status enum and note the status convention in the frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/adr.md`

## Description

- Add proposed as the first value of the H1 status enum in the adr template
- Add a status-convention paragraph to the FRONTMATTER RULES hint describing the
  lifecycle: proposed at creation, accepted or rejected on decision, deprecated on
  supersession
- Update the matching known-placeholder constant in the hydration module so the enum
  token stays whitelisted by the unresolved-placeholder scan
- Format the template with mdformat at wrap 88

## Outcome

The adr template's status enum now covers the full lifecycle including the proposed
state a freshly scaffolded ADR is in before review, and the frontmatter hint states
the convention so authors no longer have to infer it. The hydration constant
`_KNOWN_PLACEHOLDERS` carries the updated enum token; a repository-wide grep shows
these were the only two occurrences of the old three-value enum. Template annotation
and hydration tests pass (19 passed).

## Notes

The known-placeholder constant update is a one-token Python remap of the kind the
ADR's documentation-only constraint explicitly permits.
