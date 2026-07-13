---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S122
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# run vaultspec-core install --upgrade to clear the three-file reflow drift in the deployed mirror (D16)

## Scope

- `.vaultspec/rules`

## Description

- Previewed the upgrade with `vaultspec-core install --upgrade --dry-run` and read the
  per-file plan
- Applied `vaultspec-core install --upgrade` to refresh the gitignored
  `.vaultspec/rules/` mirror from the corrected `src/vaultspec_core/builtins/` source
- Deleted the stale generated orphan `.vaultspec/rules/templates/ref-audit.md` that the
  upgrade left behind
- Confirmed the mirror now ships `templates/reference.md` and no longer ships
  `templates/ref-audit.md`

## Outcome

`vaultspec-core install --upgrade` completed green: `1 created  40 updated  8 unchanged`,
zero `failed`. The created entry is `templates/reference.md` (the P06 rename landing in
the mirror); the 40 updates carry the P01-P08 prose edits into the deployed
`.vaultspec/rules/` intermediate that `sync` reads from.

The upgrade does not prune retired template files: it added `templates/reference.md` but
left the pre-rename `templates/ref-audit.md` in place, exactly the stale-orphan hazard
the S122 contract anticipated. That one stale generated file was deleted by hand. After
deletion the mirror's template set is correct: `reference.md` is present and
`ref-audit.md` is absent.

This upgrade is the prerequisite that made the S121 `sync` meaningful: `sync` propagates
from `.vaultspec/rules/`, so the mirror had to be refreshed here before `sync` could
carry the corrected source to the provider surfaces. The two Steps are recorded in plan
row order (S121 then S122) but the upgrade was necessarily applied first in execution
time; this is noted in both records.

All `.vaultspec/` changes are invisible to git because the entire `.vaultspec/` tree is
gitignored. That is expected: `.vaultspec/rules/` is the deployed mirror, reconstructed
from the committed `src/vaultspec_core/builtins/` source by `install --upgrade`, never
committed itself. The S122 commit is therefore documentation-only, carrying this Step
Record and the row closure.

## Notes

The non-pruning behavior of `install --upgrade` (added `reference.md`, retained the
stale `ref-audit.md`) is the same downstream-upgrade hazard REVIEW-005 names for external
workspaces. The Python-level remediation for that hazard is implemented in S126 (template
resolver fallback plus an actionable error message), so a stale workspace that upgrades
the package without re-running `install --upgrade` no longer hits an unhelpful "No
template found" error.
