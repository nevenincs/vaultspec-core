---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S47
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# reconcile the curator contract to the persona delegate model: orchestrate fixes through loaded personas rather than editing in-place (D11)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`

## Description

- Add the curator's Audit -> Delegate -> Verify operating mode to the Dispatch
  section: violations are fixed through the CLI fix paths and loaded agent personas
  rather than in-place edits, with a re-scan after every delegated repair (D11)
- Rewrite "Act on Flagged Items": "Address these manually or dispatch" becomes
  orchestrate per the delegate model - dispatch the appropriate persona or surface
  author-judgment items to the user
- Extend the Non-destructive requirement: the curator repairs through the CLI fix
  paths, delegates semantic repairs to loaded personas, and flags what neither path
  can fix
- Run mdformat --wrap 88 on the edited file

## Outcome

The skill and the docs-curator persona now describe the same contract: the curator
audits and orchestrates, it does not edit in-place. The P04.S25
vault-check-fix-first preference is intact - the CLI fix path remains the primary
repair route, with persona delegation as the path for what the CLI cannot fix.

## Notes

The remaining half of D11 - the persona's audit-report persistence obligation the
skill's Review section already promises - is the next Step (P05.S48). The doubled
".vault vault" phrasing in the description is P08.S109.
