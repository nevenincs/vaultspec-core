---
tags:
  - '#audit'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
  - "[[2026-07-17-upgrade-convergence-adr]]"
---

# `upgrade-convergence` audit: `convergence engine review` | PASS

## Scope

The full convergence feature: the fingerprint-verified refresh path in the
managed-entry merge (`src/vaultspec_core/core/mcps.py`), the registered
launch-convergence migration (`src/vaultspec_core/migrations`), the widened
companion seam (`src/vaultspec_core/core/commands.py`), and the two
warn-only doctor advisories (`src/vaultspec_core/core/diagnosis`,
`src/vaultspec_core/cli/spec_cmd.py`). Reviewed by an independent reviewer
persona against the governing decision's B1-B5 sub-decisions with emphasis
on refresh-gate safety (can a hand edit ever be overwritten), migration
lock-reentrancy and context binding, exit-code policy, the code-boundary
rule, and test integrity; the reviewer re-ran the four target suites.

## Findings

### review-verdict | low | pass with no critical or high findings

The refresh gate is symmetric and cannot false-match a hand edit (the
write and compare sides fingerprint the same normalized string-only
shape, key-order neutralized, on both the JSON and TOML paths). The
migration holds no conflicting locks, binds its own target context,
reports uninstalled providers and broken host files without wedging the
registry, and never creates an enrollment an operator opted out of. The
widened seam migrates every declared package atomically while foreign
entries survive. Neither advisory fails the doctor, no other signal
consumer breaks, and the new diagnosis field serializes through the
existing path. The code-boundary scan of every changed source line is
clean. Suites: 86 targeted tests passing under the reviewer, no mocks,
stubs, or skips.

### warn-count-shift | low | prek workspaces no longer fail the doctor

A prek.toml workspace with stale hooks previously failed the doctor via
the incomplete signal with a fix hint the scaffold could not honor; it now
reports the unrefreshable advisory and exits clean. Accepted as the
decision's intent (the row still renders as a warning); noted in case a
downstream consumer counted doctor warnings.

### skip-aggregation | low | migration summary aggregates all skip kinds

The migration's skipped counter folds hand-edited, pre-fingerprint, and
external skips into one number; the summary wording covers this honestly.
No action needed.

## Recommendations

- None blocking. If a future consumer needs a doctor warning count that
  includes the advisory states, that consumer should read the rendered
  rows rather than the exit code; no core change is warranted now.
