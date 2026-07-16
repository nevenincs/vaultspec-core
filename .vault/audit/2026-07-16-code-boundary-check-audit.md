---
tags:
  - '#audit'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-code-boundary-check-plan]]"
  - "[[2026-07-16-code-boundary-check-adr]]"
---

# `code-boundary-check` audit: `opt-in source-boundary scanner review` | (**status:** `PASS`)

## Scope

Read-only review of branch `feat/issue-213-code-boundary-check` versus `main`
(PR 218, GitHub issue 213) against the governing decision, plan, and research:
the checker module, the standalone verb, tests, and the regenerated CLI
reference, plus consistency with the firmware-code-boundary and commit-linkage
decisions. Reviewed by the `vaultspec-code-reviewer` persona dispatched as an
independent read-only subagent; verdict PASS with two MEDIUM recommendations,
both applied in the same session.

## Findings

### feature-filter-substring-overmatch | medium | --feature narrowing was a bare substring test (RESOLVED)

The filter over-matched short or prefix-colliding feature values and diverged
from its own docstring. Resolved beyond the reviewer's suggestion: filename
heuristics cannot split hyphenated feature and topic segments reliably, so the
filter now parses each document's frontmatter and matches the feature tag
exactly; a prefix-collision test (feature versus feature-two, single-letter
needle) locks it in.

### provider-exclusions-hardcoded-not-enum | medium | exclusion set duplicated provider names (RESOLVED)

The walk exclusions now derive from the central provider-directory enum plus
the configured docs directory at call time, keeping only VCS and cache names
as literals; a provider added to the enum is excluded the day it lands.

### docs-dir-exclusion-hardcode-mismatch | low | vault exclusion was a literal while the needle source was config-driven (RESOLVED)

Folded into the same change: the vault exclusion comes from the configured
docs directory.

### reference-projection-reconciliation | low | mirror reference diff carries pre-existing wording reconciliation (ACCEPTED)

The deployed mirror's reference diff includes stale-projection reconciliation
unrelated to this feature; the canonical builtin reference gained only the
two code-boundary lines. Benign, noted so the hunk is not read as scope creep.

### Verified clean

check all membership and order untouched (behavior byte-identical); advisory
exit contract holds on both console and JSON paths; needles are stems and
wiki-link forms only; symlink-safe iterative walk with tolerated OSErrors and
the size cap; real-filesystem tests with no test doubles; no firmware wording
changes; the shipped source and tests reference no real project records.

## Recommendations

None outstanding; both MEDIUM items were applied and re-verified (lint, type
check, 11 scanner and verb tests, vaultcore suite 488, live scan of this repo:
9 advisory warnings, exit 0). Dogfood note for triage outside this feature:
the live scan surfaces one genuine product-source violation (an ADR stem cited
in a checker docstring) and several rendered doc assets embedding vault stems.

Status: PASS. Safe to merge.
